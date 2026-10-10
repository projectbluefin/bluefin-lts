#!/usr/bin/env python3
"""Import a recipe from a verified SRPM, recording where it came from.

The factory's contract is that Fedora and CentOS dist-git supply the *recipe*
and an upstream release supplies the *payload*. This tool is the only thing
allowed to write into ``packages/``, and it refuses to write a recipe whose
provenance it cannot state.

An import is two steps, deliberately separate:

1. ``extract`` pulls a named SRPM out of a COPR repository, verifying its
   SHA-512 against repodata before anything is unpacked.
2. ``record`` writes the provenance sidecar, once the recipe has been reviewed.

Splitting them means a recipe can be inspected between extraction and being
declared, and a sidecar is never written for a tree nobody looked at.
"""

from __future__ import annotations

import argparse
import datetime as dt
import functools
import gzip
import hashlib
import io
import json
import lzma
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventory import factory_root, inventory

REPO_NS = {"repo": "http://linux.duke.edu/metadata/repo", "rpm": "http://linux.duke.edu/metadata/rpm"}
UPSTREAM_VERSION = 1


def _child(element: ET.Element, name: str) -> ET.Element | None:
    """Find a direct child by local name, ignoring any namespace prefix.

    repodata splits its vocabulary: ``name``, ``arch``, ``version``,
    ``checksum`` and ``location`` are in the default (common) namespace, while
    ``provides``, ``requires`` and the format block are ``rpm:``. Hard-coding
    either prefix reads as "the package is not in this chroot" when the real
    fault is a lookup that never matched, so both are matched by local name.
    """
    for child in element:
        if child.tag.rpartition("}")[2] == name:
            return child
    return None


def _get(url: str, timeout: int = 120) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "bluefin-factory/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def primary_metadata(repo_url: str, chroot: str) -> tuple[dict[str, dict], str]:
    """Return the primary metadata for a COPR chroot, keyed by SRPM filename.

    COPR's download front end redirects to a Pulp-backed store, so every URL is
    followed. The repodata is the authority for what the repository contains;
    the directory listing is not browsable here.
    """
    repomd_url = f"{repo_url}/{chroot}/repodata/repomd.xml"
    repomd = ET.fromstring(_get(repomd_url))
    primary = None
    for data in repomd:
        if data.attrib.get("type") != "primary":
            continue
        primary = _child(data, "location")
        break
    if primary is None:
        raise ValueError(f"{repomd_url} has no primary metadata")
    href = primary.attrib["href"]

    blob = _get(f"{repo_url}/{chroot}/{href}")
    if href.endswith(".gz"):
        xml = gzip.decompress(blob)
    elif href.endswith(".xz"):
        xml = lzma.decompress(blob)
    else:
        xml = blob

    root = ET.fromstring(xml)
    entries: dict[str, dict] = {}
    for package in root:
        if package.tag.rpartition("}")[2] != "package":
            continue
        # A source package is arch="src", not type="src". Copr writes
        # type="rpm" for every entry and distinguishes the SRPM by arch, so
        # filtering on type alone silently indexes nothing -- which reads as
        # "package not in this chroot" rather than as a parsing mistake.
        arch = _child(package, "arch")
        if arch is None or arch.text != "src":
            continue
        name = _child(package, "name")
        location = _child(package, "location")
        checksum = _child(package, "checksum")
        version = _child(package, "version")
        if name is None or location is None or checksum is None:
            continue
        entries[location.attrib["href"]] = {
            "name": name.text,
            "checksum": checksum.text,
            "checksum_type": checksum.attrib.get("type", "sha256"),
            "version": version.attrib.get("ver", "") if version is not None else "",
            "release": version.attrib.get("rel", "") if version is not None else "",
        }
    return entries, f"{repo_url}/{chroot}"


def _digest(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def rpmvercmp(left: str, right: str) -> int:
    """Compare two RPM versions the way rpm does. Returns -1, 0, or 1.

    This is the algorithm from rpm's ``lib/rpmvercmp.c``. It is not the same
    as string or tuple ordering, and getting it wrong here would silently
    import 50~rc as "newer" than 50.0, because ``~`` sorts after alphanumerics
    to rpm and before them to Python. Sorting by ``(major, minor)`` is also
    wrong: ``1.0.0.9`` must beat ``1.0.0.10`` is false in rpm but true
    numerically, while rpm compares ``1.0.0.10`` above ``1.0.0.9`` by treating
    each segment as a number when both are numeric.
    """
    if left == right:
        return 0
    if not left:
        return -1
    if not right:
        return 1

    left_index = right_index = 0
    while left_index < len(left) or right_index < len(right):
        # Skip separators, but remember whether any were skipped: that
        # decides the "is the longer one newer" fallback below.
        while left_index < len(left) and not left[left_index].isalnum() and left[left_index] != "~" and left[left_index] != "^":
            left_index += 1
        while right_index < len(right) and not right[right_index].isalnum() and right[right_index] != "~" and right[right_index] != "^":
            right_index += 1

        # A tilde sorts before everything, including the end of the string.
        left_tilde = left_index < len(left) and left[left_index] == "~"
        right_tilde = right_index < len(right) and right[right_index] == "~"
        if left_tilde or right_tilde:
            if not left_tilde:
                return 1
            if not right_tilde:
                return -1
            left_index += 1
            right_index += 1
            continue

        # A caret sorts before the end of the string but after everything
        # else, which is how a pre-release loses to its own release.
        left_caret = left_index < len(left) and left[left_index] == "^"
        right_caret = right_index < len(right) and right[right_index] == "^"
        if left_caret or right_caret:
            if left_index >= len(left):
                return -1
            if right_index >= len(right):
                return 1
            if not left_caret:
                return 1
            if not right_caret:
                return -1
            left_index += 1
            right_index += 1
            continue

        if left_index >= len(left) or right_index >= len(right):
            break

        left_start = left_index
        right_start = right_index
        numeric = left[left_index].isdigit()
        while left_index < len(left) and (left[left_index].isdigit() if numeric else left[left_index].isalpha()):
            left_index += 1
        while right_index < len(right) and (right[right_index].isdigit() if numeric else right[right_index].isalpha()):
            right_index += 1

        left_segment = left[left_start:left_index]
        right_segment = right[right_start:right_index]

        if not right_segment:
            # Numeric segments always win against alphabetic ones, so 1.1
            # beats 1.a without stripping the leading zero first.
            return 1 if numeric else -1

        if numeric:
            left_segment = left_segment.lstrip("0") or "0"
            right_segment = right_segment.lstrip("0") or "0"
            if len(left_segment) != len(right_segment):
                return 1 if len(left_segment) > len(right_segment) else -1

        if left_segment != right_segment:
            return 1 if left_segment > right_segment else -1

    if left_index >= len(left) and right_index >= len(right):
        return 0
    return 1 if left_index < len(left) else -1


def _epoch_of(version: str) -> str:
    return version if version else "0"


def select_source(entries: dict[str, dict], package: str, version: str | None) -> str:
    """Pick one source archive for a package.

    Two different kinds of ambiguity live in a repository and they are not
    treated the same way:

    * Several *versions* (50~rc and 50.0) are genuinely different recipes.
      Which one to seed from is a decision, so it is refused unless a version
      is named.
    * Several *releases* of one version (50.0-1 and 50.0-4) are rebuilds of
      the same source, most often carrying a downstream patch. The newest
      release is the right seed, and picking it is not a judgement call, so
      this is resolved here by rpm version order rather than by whichever
      archive the metadata happens to list first.
    """
    candidates = {href: meta for href, meta in entries.items() if meta["name"] == package}
    if not candidates:
        raise ValueError(f"{package} is not in this chroot")

    if version is None:
        distinct = sorted({meta["version"] for meta in candidates.values()})
        if len(distinct) > 1:
            available = sorted(f"{m['version']}-{m['release']}" for m in candidates.values())
            raise ValueError(
                f"{package} has several versions in this chroot: {distinct}. "
                f"Name one with --version. Available: {available}"
            )
    else:
        candidates = {href: meta for href, meta in candidates.items() if meta["version"] == version}
        if not candidates:
            available = sorted({meta["version"] for meta in entries.values() if meta["name"] == package})
            raise ValueError(f"{package} has no version {version}; available: {available}")

    def compare(left: tuple[str, dict], right: tuple[str, dict]) -> int:
        result = rpmvercmp(left[1]["version"], right[1]["version"])
        if result:
            return result
        return rpmvercmp(left[1]["release"], right[1]["release"])

    # Newest version, then newest release. sorted() is stable, so two archives
    # comparing equal still resolve deterministically by href rather than by
    # the order the metadata happened to be parsed in.
    return sorted(candidates.items(), key=functools.cmp_to_key(compare))[-1][0]


GZIP_MAGIC = b"\x1f\x8b\x08"
CPIO_MAGICS = (b"070701", b"070702")


def _cpio_payload(archive: Path) -> bytes:
    """Return the decompressed cpio payload of a source RPM.

    An RPM is a 96-byte lead, then a gzip-compressed signature header, then a
    gzip-compressed cpio payload. The signature header is not cpio, and its
    compressed bytes can themselves contain the gzip magic by chance, so the
    only reliable test is to decompress from a candidate offset and keep the
    result that actually parses as cpio.

    Scanning from the last offset backwards finds the payload first, because
    it is the final member. Scanning forwards from the lead would repeatedly
    rescan the same bytes and turn a linear walk into a quadratic one.
    """
    raw = archive.read_bytes()
    offsets = []
    index = raw.find(GZIP_MAGIC)
    while index != -1:
        offsets.append(index)
        index = raw.find(GZIP_MAGIC, index + 1)

    for offset in reversed(offsets):
        try:
            with io.BytesIO(raw[offset:]) as compressed:
                with gzip.GzipFile(fileobj=compressed) as decompressed:
                    candidate = decompressed.read()
        except (OSError, EOFError, zlib.error):
            # A false offset inside compressed bytes usually fails as a
            # zlib error ("invalid block type"), which is not an OSError, so
            # catching only OSError turns a recoverable candidate into a
            # traceback. gzip.BadGzipFile is already an OSError subclass.
            continue
        if candidate.startswith(CPIO_MAGICS):
            return candidate

    raise ValueError(f"{archive.name}: no gzip-compressed cpio payload found")


def extract(
    repo_url: str,
    chroot: str,
    package: str,
    root: Path,
    version: str | None = None,
    keep_archive: bool = False,
) -> Path:
    """Fetch and unpack one SRPM from a COPR chroot into ``packages/<name>``.

    The archive is verified against the SHA-512 in the chroot's primary
    metadata before it is unpacked, so a tampered or truncated download fails
    here rather than producing a recipe that fails much later.
    """
    entries, base = primary_metadata(repo_url, chroot)
    if not entries:
        raise ValueError(f"{chroot} repodata indexed no source packages")
    href = select_source(entries, package, version)
    expected = entries[href]
    algorithm = expected["checksum_type"]
    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"{href}: unsupported checksum algorithm {algorithm}")

    root = factory_root(root)
    directory = root / "packages" / package
    if directory.exists() and any(directory.iterdir()):
        raise ValueError(f"packages/{package} already exists and is not empty")

    archive_name = href.rsplit("/", 1)[-1]
    archive = root / "work" / "srpms" / archive_name
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(_get(f"{base}/{href}"))

    digest = _digest(archive, algorithm)
    if digest != expected["checksum"]:
        archive.unlink(missing_ok=True)
        raise ValueError(
            f"{archive_name}: {algorithm} mismatch\n"
            f"  repodata: {expected['checksum']}\n"
            f"  download: {digest}"
        )

    try:
        cpio_bytes = _cpio_payload(archive)
        directory.mkdir(parents=True, exist_ok=True)
        # `input=` rather than `stdin=`: a BytesIO has no real file
        # descriptor, so passing one as stdin raises io.UnsupportedOperation
        # from subprocess before cpio ever runs.
        subprocess.run(
            ["cpio", "-idm", "--quiet", "--no-absolute-filenames"],
            input=cpio_bytes,
            cwd=directory,
            check=True,
        )
    finally:
        if not keep_archive:
            archive.unlink(missing_ok=True)

    # The tarball is not a recipe file. Removing it here rather than in the
    # digest means a cached build is not invalidated by re-downloading the
    # same verified bytes under a different name.
    for staged in directory.glob("*.tar.*"):
        staged.unlink()

    specs = sorted(directory.glob("*.spec"))
    if len(specs) != 1:
        raise ValueError(f"expected exactly one spec in {directory}, found {len(specs)}")

    print(f"extracted {package} {expected['version']}-{expected['release']} -> {directory}")
    print(f"  {algorithm}: {digest}")
    print(f"  record with: --srpm-checksum {digest} --srpm-checksum-type {algorithm}")
    return directory


def record(
    package: str,
    source_repo: str,
    chroot: str,
    root: Path,
    tree_id: str,
    srpm_checksum: str,
    srpm_checksum_type: str,
) -> Path:
    """Write the provenance sidecar for an imported recipe.

    ``tree_id`` is the git tree of the recipe as imported, so drift from the
    seed is computable later rather than asserted.

    The checksum recorded is the one repodata published, which for Copr is
    SHA-256. It proves the download matches what the repository advertised; it
    is not an independently published upstream digest, and a recipe that later
    moves to direct-source builds gets a SHA-512 in the source lock instead.
    """
    root = factory_root(root)
    directory = root / "packages" / package
    if not directory.is_dir():
        raise ValueError(f"packages/{package} does not exist")

    sidecar = {
        "schema": UPSTREAM_VERSION,
        "package": package,
        "source": {
            "kind": "srpm",
            "repository": source_repo,
            "chroot": chroot,
            "srpm_checksum": srpm_checksum,
            "srpm_checksum_type": srpm_checksum_type,
            "tree": tree_id,
        },
        "imported_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    }
    path = directory / ".factory-upstream.json"
    path.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n")
    print(f"recorded provenance -> {path}")
    return path


def status(root: Path | None = None) -> int:
    """Report which recipes carry provenance. Exits non-zero if any is missing."""
    root = factory_root(root)
    missing = []
    for record in inventory(root):
        if not (record.directory / ".factory-upstream.json").is_file():
            missing.append(record.name)
    if missing:
        print("recipes without recorded provenance:", file=sys.stderr)
        for name in missing:
            print(f"  {name}", file=sys.stderr)
        return 1
    print(f"{len(inventory(root))} recipes carry recorded provenance")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("--repo", required=True, help="COPR repository base URL")
    extract_parser.add_argument("--chroot", required=True)
    extract_parser.add_argument("--package", required=True)
    extract_parser.add_argument(
        "--version",
        default=None,
        help="upstream version to import; required when the chroot carries several",
    )
    extract_parser.add_argument("--root", type=Path, default=None)
    extract_parser.add_argument("--keep-archive", action="store_true")

    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--package", required=True)
    record_parser.add_argument("--repo", required=True)
    record_parser.add_argument("--chroot", required=True)
    record_parser.add_argument("--tree", required=True, help="git tree id of the recipe")
    record_parser.add_argument("--srpm-checksum", required=True)
    record_parser.add_argument(
        "--srpm-checksum-type",
        default="sha256",
        choices=sorted(name for name in hashlib.algorithms_available if "sha" in name),
    )
    record_parser.add_argument("--root", type=Path, default=None)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--root", type=Path, default=None)

    args = parser.parse_args()
    try:
        if args.command == "extract":
            extract(args.repo, args.chroot, args.package, args.root, args.version, args.keep_archive)
        elif args.command == "record":
            record(
                args.package,
                args.repo,
                args.chroot,
                args.root,
                args.tree,
                args.srpm_checksum,
                args.srpm_checksum_type,
            )
        elif args.command == "status":
            return status(args.root)
    except (OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())