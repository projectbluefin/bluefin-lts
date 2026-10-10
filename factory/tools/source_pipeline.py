#!/usr/bin/env python3
"""Fetch and verify the upstream source for each recipe, before any build.

The factory's contract is that a build never downloads anything. A recipe's
Source0 is fetched here, verified against a digest recorded in
``config/upstream-sources.json``, and staged beside the spec. A package whose
lock is missing is not eligible for a build: this exits non-zero rather than
falling back to whatever the build root happens to serve.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventory import Record, factory_root, inventory

# Archive extensions a spec's Source0 can plausibly be. Anything else (a bare
# tarball with no suffix, a directory) is a lock the operator has to stage.
ARCHIVE_SUFFIXES = (".tar.gz", ".tar.xz", ".tar.bz2", ".tar.zst", ".tar.lz", ".tar.lzma", ".tgz")


def _fetch(url: str, timeout: int = 300) -> bytes:
    """Download a URL, retrying a transient failure.

    Some upstreams are intermittently unavailable. gitlab.freedesktop.org
    serves `/-/archive/<tag>/` URLs and answers 500 on a fraction of requests
    -- the fontconfig source was refused on one CI run and served the same
    bytes moments later, with a digest that matched the lock exactly. Without
    a retry that is a random red build on a healthy source.

    Only transient answers are retried. A 404 is retried zero times: the URL is
    wrong, and hammering a host that is certain to say no helps nobody. 429 and
    5xx are retried, because those mean "not now".

    Retries are announced rather than silent. A source that needed three
    attempts is a signal about its host, and hiding that makes the gate look
    more reliable than it is.
    """
    attempts = 4
    delay = 2.0
    last: OSError | None = None

    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers={"User-Agent": "bluefin-factory/1"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code < 500 and error.code != 429:
                raise
            last = error
        except OSError as error:
            last = error

        if attempt == attempts:
            break
        print(
            f"  attempt {attempt}/{attempts} failed for {url}: {last}; "
            f"retrying in {delay:.0f}s",
            file=sys.stderr,
        )
        time.sleep(delay)
        delay *= 2

    raise OSError(f"{url}: failed after {attempts} attempts: {last}")


def _digest(blob: bytes, algorithm: str) -> str:
    return hashlib.new(algorithm, blob).hexdigest()


def source_filename(url: str) -> str:
    """The local filename rpmbuild gives a downloaded source.

    RPM's ``#/filename`` syntax renames the downloaded archive locally. It
    does not select a directory inside that archive.
    """
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    return (parsed.fragment or parsed.path).rstrip("/").rsplit("/", 1)[-1]


def fetch_source(record: Record, root: Path, allow_missing: bool = False) -> list[Path] | None:
    """Fetch and verify every one of a recipe's sources.

    All of them, not just Source0. A recipe with a second downloadable Source
    -- glycin's vendored libjxl, malcontent's libgsystemservice -- fails
    `rpmbuild -bs` without it, and the failure names the missing archive
    rather than the lock that failed to fetch it.

    Each URL is fetched directly from upstream. ``fallback_urls`` exist so one
    host being down does not block a build, but every one is verified against
    the same recorded digest, so a fallback cannot substitute different bytes.
    """
    root = factory_root(root)
    lock = record.lock
    if not lock:
        if allow_missing:
            return None
        raise ValueError(f"{record.name}: no entry in config/upstream-sources.json")

    if lock.get("no_upstream_source"):
        return None

    if record.blocked:
        raise ValueError(
            f"{record.name}: not buildable by this factory.\n  {record.blocked_reason}"
        )

    sources = record.sources
    if not sources:
        raise ValueError(f"{record.name}: lock lists no sources")

    staged: list[Path] = []
    for index, source in enumerate(sources):
        label = "Source0" if index == 0 else f"Source{index}"

        url = source.get("url", "")
        if not url:
            raise ValueError(f"{record.name}: {label} has no url")

        expected = source.get("sha512") or source.get("sha256")
        if not expected:
            raise ValueError(f"{record.name}: {label} has no recorded digest")
        algorithm = source.get("checksum_type") or (
            "sha256" if source.get("sha256") else "sha512"
        )

        filename = source.get("filename") or source_filename(url)
        path = record.directory / filename
        if path.is_file() and _digest(path.read_bytes(), algorithm) == expected:
            staged.append(path)
            continue

        if url.startswith("generated:cargo-vendor/"):
            from tools.generate_vendor import generate
            archive = record.directory / source["generated"]["archive"]
            if archive not in staged:
                raise ValueError(f"{record.name}: vendor input must be verified first")
            generate(archive, path, source["generated"].get("lockfile", "Cargo.lock"))
            if _digest(path.read_bytes(), algorithm) != expected:
                path.unlink()
                raise ValueError(f"{record.name}: generated vendor digest mismatch")
            staged.append(path)
            continue
        # .sig and .asc are detached signatures, not payload. They still have
        # to be staged -- the spec verifies against them -- so they are a
        # legitimate source file even though they are not an archive.
        if not filename.endswith(ARCHIVE_SUFFIXES) and not filename.endswith((".sig", ".asc")):
            raise ValueError(
                f"{record.name}: {label}: {filename!r} is neither an archive nor a "
                "signature; the source policy covers neither"
            )

        failures = []
        blob = None
        for candidate in [url, *source.get("fallback_urls", [])]:
            try:
                fetched = _fetch(candidate)
            except OSError as error:
                failures.append(f"{candidate}: {error}")
                continue
            digest = _digest(fetched, algorithm)
            if digest != expected:
                failures.append(f"{candidate}: {algorithm} mismatch (got {digest})")
                continue
            blob = fetched
            break

        if blob is None:
            raise ValueError(
                f"{record.name}: {label}: no source verified\n  " + "\n  ".join(failures)
            )

        path = record.directory / filename
        path.write_bytes(blob)
        staged.append(path)
    return staged


def stage(package: str, root: Path | None, output: Path | None = None) -> int:
    """Fetch one named package's source."""
    root = factory_root(root)
    matches = [record for record in inventory(root) if record.name == package]
    if not matches:
        raise ValueError(f"{package} is not a recipe in this factory")
    staged = fetch_source(matches[0], root)
    if output is not None and staged is not None:
        output.mkdir(parents=True, exist_ok=True)
        for path in staged:
            (output / path.name).write_bytes(path.read_bytes())
    if staged is None:
        print(f"{package}: no upstream source by policy")
    else:
        print(f"{package}: staged {staged}")
    return 0


def stage_all(root: Path | None = None) -> int:
    """Fetch every recipe's source. Reports all failures, not just the first."""
    root = factory_root(root)
    failures = []
    for record in inventory(root):
        try:
            staged = fetch_source(record, root)
        except (OSError, ValueError) as error:
            failures.append(f"{record.name}: {error}")
            continue
        print(f"staged {record.name}" if staged else f"{record.name}: no upstream source")
    if failures:
        print("\nfailures:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    return 0


def verify_staged(root: Path | None = None, package: str | None = None) -> int:
    """Re-verify already-staged sources without downloading anything.

    This runs inside the build container, after the source was fetched, so a
    source that was swapped between staging and build fails here rather than
    producing an RPM from bytes nobody verified.
    """
    root = factory_root(root)
    failures = []
    checked = 0
    for record in inventory(root):
        if package and record.name != package:
            continue
        lock = record.lock
        if lock.get("no_upstream_source"):
            continue
        for index, source in enumerate(record.sources):
            label = "Source0" if index == 0 else f"Source{index}"
            filename = source.get("filename") or source_filename(source.get("url", ""))
            staged = record.directory / filename
            if not filename or not staged.is_file():
                failures.append(
                    f"{record.name}: {label}: {filename or '(no filename)'} is not staged"
                )
                continue
            algorithm = source.get("checksum_type") or (
                "sha256" if source.get("sha256") else "sha512"
            )
            expected = source.get("sha512") or source.get("sha256")
            actual = _digest(staged.read_bytes(), algorithm)
            checked += 1
            if actual != expected:
                failures.append(
                    f"{record.name}: {label}: {filename} fails {algorithm} verification"
                )

    if failures:
        print("staged source verification failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print(f"verified {checked} staged sources")
    return 0


def report(root: Path | None = None) -> int:
    """Print the resolved source for every recipe."""
    root = factory_root(root)
    rows = []
    for record in inventory(root):
        if not record.lock:
            rows.append((record.name, "UNLOCKED", "-"))
        elif record.no_upstream_source:
            rows.append((record.name, "no-upstream-source", record.version))
        else:
            urls = " ".join(source.get("url", "") for source in record.sources)
            count = len(record.sources)
            # The count is shown because a recipe with several sources is the
            # one that breaks when the lock only carries the first.
            suffix = f" ({count} sources)" if count > 1 else ""
            rows.append((record.name, f"{record.version}{suffix}", urls))
    width = max(len(row[0]) for row in rows) if rows else 10
    for name, version, url in rows:
        print(f"{name:<{width}}  {version:<28}  {url}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage_parser = subparsers.add_parser("stage")
    stage_parser.add_argument("package")
    stage_parser.add_argument("--root", type=Path, default=None)
    stage_parser.add_argument("--output", type=Path, default=None)

    all_parser = subparsers.add_parser("stage-all")
    all_parser.add_argument("--root", type=Path, default=None)

    verify_parser = subparsers.add_parser("verify-staged")
    verify_parser.add_argument("--root", type=Path, default=None)
    verify_parser.add_argument("--package", default=None)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--root", type=Path, default=None)

    args = parser.parse_args()
    try:
        if args.command == "stage":
            return stage(args.package, args.root, args.output)
        if args.command == "stage-all":
            return stage_all(args.root)
        if args.command == "verify-staged":
            return verify_staged(args.root, args.package)
        if args.command == "report":
            return report(args.root)
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
