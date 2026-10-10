#!/usr/bin/env python3
"""Render ``config/upstream-sources.json`` from the recipes themselves.

Each recipe's Source0 is a macro expression, not a URL: ``%{version}``,
``%{major_version}``, ``%{name}``. Resolving those needs rpmspec and the EL10
macro definitions, so this runs inside the pinned build root and the resolved
value is written to the lock.

The lock is then the authority: ``source_pipeline.py`` fetches the recorded URL
and verifies the recorded digest, and never asks the spec again. That split is
what makes a build reproducible -- the spec can be edited to point somewhere
else, and the lock has to be re-rendered deliberately for that to take effect.

Two things this deliberately does not do:

* It does not invent a digest. An archive that will not download leaves the
  entry unresolved and named in the report, rather than being written with a
  checksum nothing was checked against.
* It does not follow the Fedora lookaside. The EL10 specs point at upstream
  release URLs, which is what the factory's source policy requires; where a
  spec points at the lookaside, that is reported rather than silently accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.buildroot import read_pin
from tools.inventory import factory_root, inventory
from tools.source_pipeline import source_filename
from tools.source_pipeline import _fetch as _fetch_url  # noqa: E402

SCHEMA = 1


def buildroot_image(root: Path) -> str:
    """The immutable buildroot reference used for RPM macro expansion."""
    return read_pin(root)


def resolved_sources(root: Path, image: str, engine: str) -> dict[str, list[str]]:
    """Ask rpmspec, inside the build root, what each recipe's Source0 expands to."""
    script = r"""#!/bin/bash
set -euo pipefail
outdir="$1"
mkdir -p "$outdir"
dnf -y install rpm-build >/dev/null 2>&1 || true
for spec in /packages/*/*.spec; do
  name=$(basename "$(dirname "$spec")")
  # rpmspec --parse expands every macro and resolves conditionals, so the
  # Source lines it prints are the ones rpmbuild will use. %SOURCE is not
  # consulted: `rpmspec -P --qf '%{SOURCE}'` answers with the whole parsed
  # spec rather than the URL, which silently yields no source at all.
  rpmspec --parse "$spec" 2>/dev/null \
    | sed -n 's/^\(Source[0-9]*\):[ \t]*\(.*\)$/\2/p' \
    > "$outdir/$name.sources" || : > "$outdir/$name.sources"
done
"""
    outdir = root / "work" / "sources"
    outdir.mkdir(parents=True, exist_ok=True)
    for stale in outdir.glob("*.sources"):
        stale.unlink()

    script_path = outdir / "render.sh"
    script_path.write_text(script)
    script_path.chmod(0o755)

    result = subprocess.run(
        [
            engine, "run", "--rm",
            "-v", f"{root / 'packages'}:/packages:ro,Z",
            "-v", f"{outdir}:/out:Z",
            "-v", f"{script_path}:/render.sh:ro,Z",
            image,
            "bash", "/render.sh", "/out",
        ],
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"could not resolve sources in {image}")

    resolved: dict[str, list[str]] = {}
    for path in sorted(outdir.glob("*.sources")):
        entries = [line.strip() for line in path.read_text().splitlines() if line.strip()]
        resolved[path.stem] = entries
    return resolved


def fetch_digest(url: str, algorithm: str = "sha512", timeout: int = 300) -> str | None:
    """Download a source once to compute its digest. None if unreachable.

    Retries through the shared fetcher: rendering touches every unlocked source
    in the factory, so one flaky host would otherwise abort a run that has
    already done most of its work.
    """
    try:
        blob = _fetch_url(url, timeout=timeout)
    except OSError:
        return None
    return hashlib.new(algorithm, blob).hexdigest()


def is_local(name: str) -> bool:
    """True for a Source that is a file in the recipe, not a download."""
    return not name.startswith(("http://", "https://", "ftp://"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--engine", default="podman")
    parser.add_argument("--image", default=None, help="build root image; default is the pin")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="resolve URLs but do not fetch, leaving digests unresolved",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = factory_root(args.root)
    image = args.image
    if image is None:
        # Resolve macros against the same immutable image as binary builds.
        image = buildroot_image(root)

    print(f"resolving sources in {image} ...", file=sys.stderr)
    resolved = resolved_sources(root, image, args.engine)

    entries = []
    unresolved = []
    lookaside = []
    local_only = []
    blocked: list[tuple[str, list[str]]] = []

    # Existing digests, keyed by URL, so a re-render fetches only what
    # actually changed. Re-downloading every archive in the factory to
    # re-render a lock is slow, hammers upstream for nothing, and makes the
    # tool something people avoid running.
    previous: dict[str, dict] = {}
    existing = root / "config" / "upstream-sources.json"
    if existing.is_file():
        try:
            document = json.loads(existing.read_text())
        except json.JSONDecodeError:
            document = {}
        for entry in document.get("packages", []):
            for source in lock_sources(entry):
                if source.get("url"):
                    previous[source["url"]] = source

    for record in inventory(root):
        # Every downloadable source, not just the first. A recipe with a
        # second Source -- glycin's vendored libjxl, malcontent's
        # libgsystemservice -- cannot build without it, and locking only
        # Source0 produces a recipe that passes validation and fails in
        # rpmbuild.
        all_sources = resolved.get(record.name, [])
        remote = [item for item in all_sources if not is_local(item)]

        # A Source that is a bare filename, is not a URL, and is not present
        # in the recipe, cannot be fetched and cannot be built. glycin and
        # gnome-user-share carry a `cargo vendor` tarball generated by hand;
        # malcontent bundles gvdb and tinycdb. These are recorded as blocked
        # rather than silently locked to nothing -- a recipe that passes
        # validation and then fails in rpmbuild names the missing archive and
        # not the lock that failed to provide it.
        generated = [source for source in previous.values()
                     if source.get("generated") and source.get("filename") in all_sources]
        absent = [
            item
            for item in all_sources
            if is_local(item) and not (record.directory / item).is_file()
            and item not in {source["filename"] for source in generated}
        ]

        if not remote:
            local_only.append(record.name)
            entries.append({
                "name": record.name,
                "version": version_of(record),
                "no_upstream_source": True,
            })
            continue

        locked = []
        for url in remote:
            if "src.fedoraproject.org/repo/pkgs" in url:
                lookaside.append((record.name, url))

            entry = {"url": url, "filename": source_filename(url)}

            cached = previous.get(url)
            if cached and cached.get("sha512"):
                entry["sha512"] = cached["sha512"]
                entry["checksum_type"] = cached.get("checksum_type", "sha512")
                locked.append(entry)
                continue

            if args.no_download:
                unresolved.append((record.name, url))
                locked.append(entry)
                continue

            digest = fetch_digest(url)
            if digest is None:
                unresolved.append((record.name, url))
                locked.append(entry)
                continue
            entry["sha512"] = digest
            entry["checksum_type"] = "sha512"
            locked.append(entry)

        locked.extend(generated)
        entry = {
            "name": record.name,
            "version": version_of(record),
            "sources": locked,
        }
        if absent:
            blocked.append((record.name, absent))
            entry["blocked"] = True
            entry["blocked_reason"] = (
                "references sources that are neither downloadable nor present in "
                "the recipe: " + ", ".join(absent)
            )
        entries.append(entry)

    document = {
        "schema": SCHEMA,
        "packages": sorted(entries, key=lambda item: item["name"]),
    }
    rendered = json.dumps(document, indent=2) + "\n"

    target = args.output or (root / "config" / "upstream-sources.json")
    if args.write:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered)
        print(f"wrote {target}", file=sys.stderr)
    else:
        print(rendered, end="")

    total_sources = sum(len(entry.get("sources", [])) for entry in entries)
    locked_sources = sum(
        1
        for entry in entries
        for source in entry.get("sources", [])
        if source.get("sha512")
    )
    multi = sum(1 for entry in entries if len(entry.get("sources", [])) > 1)
    print(
        f"\n{locked_sources} of {total_sources} sources locked across "
        f"{len(entries)} recipes ({multi} with more than one source)",
        file=sys.stderr,
    )
    if local_only:
        print(
            f"{len(local_only)} recipe(s) have no downloadable source (config-only): "
            + ", ".join(local_only),
            file=sys.stderr,
        )
    if lookaside:
        print(
            f"\n{len(lookaside)} recipe(s) point at the Fedora lookaside, which the "
            "source policy does not accept as a primary URL:",
            file=sys.stderr,
        )
        for name, url in lookaside:
            print(f"  {name}: {url}", file=sys.stderr)
    if blocked:
        print(
            f"\n{len(blocked)} recipe(s) are marked blocked: they reference a source "
            "that is neither downloadable nor committed. They cannot be built "
            "until that source is either committed to the recipe or produced by a "
            "documented step:",
            file=sys.stderr,
        )
        for name, absent in blocked:
            print(f"  {name}: {', '.join(absent)}", file=sys.stderr)
    if unresolved:
        print(
            f"\n{len(unresolved)} recipe(s) could not be fetched; their entries carry "
            "no digest and will not build until one is recorded:",
            file=sys.stderr,
        )
        for name, url in unresolved:
            print(f"  {name}: {url}", file=sys.stderr)
    return 0


def version_of(record) -> str:
    """Read Version out of the spec without rpmspec, for the lock's benefit.

    Deliberately not the expanded value: the lock records what the spec says,
    and rpmspec is not available outside the build root.
    """
    for line in record.spec.read_text(errors="replace").splitlines():
        if line.lower().startswith("version:"):
            return line.split(":", 1)[1].strip()
    return ""


def lock_sources(entry: dict) -> list[dict]:
    """Every locked source in a lock entry, old flat shape or new list shape."""
    sources = entry.get("sources")
    if isinstance(sources, list) and sources:
        return sources
    if entry.get("url"):
        return [{
            "url": entry["url"],
            "filename": entry.get("filename", ""),
            "sha512": entry.get("sha512"),
            "checksum_type": entry.get("checksum_type", "sha512"),
        }]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
