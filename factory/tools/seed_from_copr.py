#!/usr/bin/env python3
"""Seed the recipe set from a COPR chroot, in one transaction.

Importing 70-odd packages one command at a time is slow and easy to leave
half-finished. This drives ``import_srpm.py`` over a whole chroot, writing
provenance for each package, and then records the tree ids.

The order here is not alphabetical but it does not need to be: build order is
solved from BuildRequires, not from the order recipes were imported in.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.import_srpm import primary_metadata, rpmvercmp, select_source
from tools.inventory import factory_root


def available(entries: dict[str, dict]) -> dict[str, list[str]]:
    """Map package name -> the versions the chroot carries for it."""
    found: dict[str, list[str]] = {}
    for meta in entries.values():
        found.setdefault(meta["name"], [])
    for meta in entries.values():
        found[meta["name"]].append(meta["version"])
    return {name: sorted(set(versions)) for name, versions in found.items()}


def pick_version(versions: list[str], prefer_newest: bool) -> str | None:
    """Choose one version from those a package has in this chroot.

    "Newest" is by rpm version order, not string order. The difference is not
    cosmetic here: this chroot carries both ``50.0`` and ``50~rc`` for most of
    the GNOME stack, and a string sort puts the release candidate last while
    rpm puts it first, because ``~`` sorts before everything including the end
    of the string. A string sort would seed the whole desktop from RCs.
    """
    if len(versions) == 1:
        return versions[0]
    if not prefer_newest:
        return None
    # cmp_to_key, not key=rpmvercmp: rpmvercmp takes two arguments and
    # cmp_to_key is what adapts it into a single-argument sort key.
    return sorted(versions, key=functools.cmp_to_key(rpmvercmp))[-1]


def git_tree_id(directory: Path) -> str:
    """Compute the git tree id of a recipe directory.

    ``git add`` writes to the real index, which would stage a file the
    operator has not decided to commit, so a throwaway index is used.
    """
    git_dir = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    with tempfile.TemporaryDirectory() as scratch:
        env = {
            **os.environ,
            "GIT_INDEX_FILE": str(Path(scratch) / "index"),
        }
        subprocess.run(
            ["git", "--git-dir", git_dir, "add", "--", str(directory)],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        tree = subprocess.run(
            ["git", "--git-dir", git_dir, "write-tree"],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        ).stdout.strip()
    return tree


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--chroot", required=True)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--package",
        action="append",
        default=None,
        help="import only this package; repeatable",
    )
    parser.add_argument(
        "--version",
        action="append",
        default=None,
        help="version for the matching --package, or 'newest'; repeatable",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "refuse to guess when a package has several versions, instead of "
            "taking the newest by rpm version order"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = factory_root(args.root)
    entries, _ = primary_metadata(args.repo, args.chroot)
    catalogue = available(entries)

    if args.package:
        requested = args.package
    else:
        requested = sorted(catalogue)

    versions = dict(zip(args.package or [], args.version or []))

    imported, skipped, failed = [], [], []
    for name in requested:
        if name not in catalogue:
            skipped.append((name, "not in this chroot"))
            continue
        version = versions.get(name)
        if version is None and len(catalogue[name]) > 1:
            if args.strict:
                skipped.append((name, f"several versions available: {sorted(catalogue[name])}"))
                continue
            # Newest by rpm version order. This is the default because the
            # chroot carries 50~rc alongside 50.0 for most of the stack, and
            # seeding from release candidates would mean starting the GNOME
            # 51 work from pre-releases.
            version = pick_version(catalogue[name], True)
        elif version == "newest":
            version = pick_version(catalogue[name], True)

        try:
            href = select_source(entries, name, version)
        except ValueError as error:
            failed.append((name, str(error)))
            continue

        if args.dry_run:
            imported.append((name, version or "", href))
            continue

        result = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "import_srpm.py"),
                "extract",
                "--repo", args.repo,
                "--chroot", args.chroot,
                "--package", name,
                "--root", str(root),
                *([ "--version", version ] if version else []),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            failed.append((name, result.stderr.strip() or result.stdout.strip()))
            continue

        metadata = entries[href]
        directory = root / "packages" / name
        tree = git_tree_id(directory)
        record = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "import_srpm.py"),
                "record",
                "--repo", args.repo,
                "--chroot", args.chroot,
                "--package", name,
                "--tree", tree,
                "--srpm-checksum", metadata["checksum"],
                "--srpm-checksum-type", metadata["checksum_type"],
                "--root", str(root),
            ],
            capture_output=True,
            text=True,
        )
        if record.returncode != 0:
            failed.append((name, record.stderr.strip() or record.stdout.strip()))
            continue
        imported.append((name, f"{metadata['version']}-{metadata['release']}", tree))

    print(json.dumps({
        "imported": [{"package": n, "version": v, "tree": t} for n, v, t in imported],
        "skipped": [{"package": n, "reason": r} for n, r in skipped],
        "failed": [{"package": n, "error": e} for n, e in failed],
    }, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())