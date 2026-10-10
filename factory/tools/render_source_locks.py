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

from tools.buildroot import buildroot_config
from tools.inventory import factory_root, inventory

SCHEMA = 1


def buildroot_image(root: Path) -> str:
    """The build root image reference without its digest."""
    return str(buildroot_config(root)["image"])


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
    """Download a source once to compute its digest. None if unreachable."""
    request = urllib.request.Request(url, headers={"User-Agent": "bluefin-factory/1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            hasher = hashlib.new(algorithm)
            for block in iter(lambda: response.read(1 << 20), b""):
                hasher.update(block)
            return hasher.hexdigest()
    except (OSError, ValueError):
        return None


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
        # The image reference without its digest: a container runtime cannot
        # pull a `name@sha256:` reference. The digest is enforced by
        # tools/buildroot.py at build time, not by this resolver.
        image = buildroot_image(root)

    print(f"resolving sources in {image} ...", file=sys.stderr)
    resolved = resolved_sources(root, image, args.engine)

    entries = []
    unresolved = []
    lookaside = []
    local_only = []

    for record in inventory(root):
        sources = resolved.get(record.name, [])
        # Source0 is the payload; later sources are patches and generated
        # inputs the recipe references by name, and the factory only locks
        # what a build downloads.
        primary = next((item for item in sources if not is_local(item)), None)
        if primary is None:
            local_only.append(record.name)
            entries.append({
                "name": record.name,
                "version": _version_of(record),
                "no_upstream_source": True,
            })
            continue

        if "src.fedoraproject.org/repo/pkgs" in primary:
            lookaside.append((record.name, primary))

        entry = {
            "name": record.name,
            "version": _version_of(record),
            "url": primary,
            "filename": primary.rsplit("/", 1)[-1],
        }
        if args.no_download:
            unresolved.append((record.name, primary))
            entries.append(entry)
            continue

        digest = fetch_digest(primary)
        if digest is None:
            unresolved.append((record.name, primary))
            entries.append(entry)
            continue
        entry["sha512"] = digest
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

    resolved_count = sum(1 for entry in entries if entry.get("sha512"))
    print(
        f"\n{resolved_count} of {len(entries)} recipes have a verified source lock",
        file=sys.stderr,
    )
    if local_only:
        print(
            f"{len(local_only)} recipe(s) have no Source0 URL (config-only): "
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
    if unresolved:
        print(
            f"\n{len(unresolved)} recipe(s) could not be fetched; their entries carry "
            "no digest and will not build until one is recorded:",
            file=sys.stderr,
        )
        for name, url in unresolved:
            print(f"  {name}: {url}", file=sys.stderr)
    return 0


def _version_of(record) -> str:
    """Read Version out of the spec without rpmspec, for the lock's benefit."""
    import re

    for line in record.spec.read_text(errors="replace").splitlines():
        if line.lower().startswith("version:"):
            return line.split(":", 1)[1].strip()
    return ""


if __name__ == "__main__":
    raise SystemExit(main())