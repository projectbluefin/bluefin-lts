#!/usr/bin/env python3
"""Validate the factory's own configuration.

Everything checked here is a precondition for a build being trustworthy, and
none of it can be deferred to the build job:

* every recipe has recorded provenance, so we can say where it came from;
* every recipe has a source lock, so no build downloads anything;
* every lock entry names a recipe that exists, so the lock cannot rot into
  describing a package that was deleted;
* the build root is pinned by digest;
* the factory contract sidecar is pinned by commit.

A recipe that fails any of these is not "probably fine", it is a package whose
provenance cannot be stated.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventory import factory_root, inventory

REQUIRED_LOCK_FIELDS = ("url", "sha512")


def check_provenance(root: Path) -> list[str]:
    """Every recipe must record where it came from."""
    problems = []
    for record in inventory(root):
        sidecar = record.directory / ".factory-upstream.json"
        if not sidecar.is_file():
            problems.append(f"{record.name}: no .factory-upstream.json")
            continue
        try:
            document = json.loads(sidecar.read_text())
        except json.JSONDecodeError as error:
            problems.append(f"{record.name}: unreadable provenance: {error}")
            continue
        source = document.get("source", {})
        for field in ("kind", "repository", "tree", "imported_at"):
            if not source.get(field) and not document.get(field):
                problems.append(f"{record.name}: provenance has no {field}")
        if source.get("kind") == "srpm":
            if not source.get("srpm_checksum"):
                problems.append(f"{record.name}: provenance records no srpm_checksum")
            if not source.get("chroot"):
                problems.append(f"{record.name}: provenance records no chroot")
    return problems


def check_locks(root: Path) -> list[str]:
    """Recipes and locks must correspond exactly, in both directions."""
    problems = []
    records = inventory(root)
    names = {record.name for record in records}

    for record in records:
        if not record.lock:
            problems.append(f"{record.name}: no entry in config/upstream-sources.json")
            continue
        if record.no_upstream_source:
            if record.spec.stat().st_size == 0:
                problems.append(f"{record.name}: spec is empty")
            continue
        for field in REQUIRED_LOCK_FIELDS:
            if not record.lock.get(field):
                problems.append(f"{record.name}: lock has no {field}")
        if record.version and record.no_upstream_source:
            problems.append(f"{record.name}: declares both a version and no_upstream_source")

    lock_path = root / "config" / "upstream-sources.json"
    if lock_path.is_file():
        document = json.loads(lock_path.read_text())
        for entry in document.get("packages", []):
            if entry.get("name") not in names:
                problems.append(
                    f"config/upstream-sources.json: {entry.get('name')} has no recipe in packages/"
                )
    return problems


def check_buildroot(root: Path) -> list[str]:
    """The build root must be pinned by digest, and state its repositories."""
    path = root / "config" / "buildroot.json"
    if not path.is_file():
        return ["config/buildroot.json: missing; the build root must be pinned"]
    try:
        document = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        return [f"config/buildroot.json: {error}"]

    if not isinstance(document, dict):
        return ["config/buildroot.json: expected an object"]

    problems = []
    for field in ("image", "digest"):
        if not document.get(field):
            problems.append(f"config/buildroot.json: no {field}")

    digest = str(document.get("digest", ""))
    if digest and (not digest.startswith("sha256:") or len(digest) != 71):
        problems.append(
            f"config/buildroot.json: digest {digest!r} is not a sha256. A tag "
            "alone means the factory builds against whatever the tag resolved "
            "to, which is neither reproducible nor attestable."
        )

    # CRB ships disabled in c10s and several build roots for this stack live
    # only there. A buildroot.json that forgets it produces a BuildRequires
    # failure naming meson, which does not say the repository was off.
    if "crb" not in (document.get("repositories") or []):
        problems.append(
            "config/buildroot.json: repositories does not include crb. "
            "meson, ninja-build, wayland-devel and gcc-g++ are CRB-only on EL10."
        )

    if not document.get("bootstrap"):
        problems.append("config/buildroot.json: no bootstrap packages")
    return problems


def check_dependencies(root: Path) -> list[str]:
    """No tool may import a third-party module.

    Cheap to check, and the failure it prevents is expensive and confusing: a
    ModuleNotFoundError names a module and nothing about the fact that CI never
    installed it.
    """
    problems = []
    for tool in sorted((root / "tools").glob("*.py")):
        tree = ast.parse(tool.read_text(), filename=str(tool))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                # A relative import (level > 0) is this factory's own package.
                if node.level and node.level > 0:
                    continue
                if node.module:
                    names = [node.module.split(".")[0]]
            for name in names:
                # `tools` is this factory's own package, reached via the
                # sys.path entry every tool sets up.
                if name in sys.stdlib_module_names or name == "tools":
                    continue
                problems.append(
                    f"{tool.name}: imports {name!r}, which is not in the standard "
                    "library. CI installs no Python packages, so this fails on "
                    "the runner. Use the stdlib, as build_scripts/scripts/"
                    "read-packages does."
                )
    return problems


def check_contract(root: Path) -> list[str]:
    """The shared factory contract must be pinned by commit."""
    problems = []
    path = root / "config" / "factory-contract.json"
    if not path.is_file():
        return ["config/factory-contract.json: missing; the factory contract must be pinned"]
    document = json.loads(path.read_text())
    for field in ("repository", "commit", "pinned_at"):
        if not document.get(field):
            problems.append(f"config/factory-contract.json: no {field}")
    commit = str(document.get("commit", ""))
    if commit and len(commit) != 40 or not all(c in "0123456789abcdef" for c in commit):
        problems.append(f"config/factory-contract.json: commit {commit!r} is not a full sha")
    return problems


MONTHS = {
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
}
WEEKDAYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


def check_changelog_dates(root: Path) -> list[str]:
    """Changelog entries must begin with a real weekday.

    rpmbuild rejects the whole spec over one malformed date, and the
    rejection names the file rather than the entry, so it costs a build to
    discover. This is the mistake Packit's SRPM gate would catch in seconds --
    which is precisely why it is cheap to catch here too.
    """
    problems = []
    for record in inventory(root):
        text = record.spec.read_text(errors="replace")
        in_changelog = False
        for index, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("%changelog"):
                in_changelog = True
                continue
            if in_changelog and stripped.startswith("%"):
                in_changelog = False
            if not in_changelog or not stripped.startswith("* "):
                continue
            rest = stripped[2:].strip()
            if not rest:
                continue
            first = rest.split()[0].rstrip(",").lower()
            # A weekday is the only token allowed to lead an entry. A
            # lowercase word here is a broken date ("mon Apr 07") or, in a
            # body rather than a changelog, prose -- which is why this tracks
            # section context instead of scanning the whole file.
            if first not in WEEKDAYS:
                problems.append(
                    f"{record.name}: {record.spec.name}:{index}: "
                    f"changelog entry does not begin with a weekday: {first!r}"
                )
    return problems


def check_spec_sanity(root: Path) -> list[str]:
    """Catch the spec mistakes that are cheap to detect without building."""
    problems = []
    for record in inventory(root):
        text = record.spec.read_text(errors="replace")
        for tag in ("Name:", "Version:", "Release:", "Summary:", "License:"):
            if not any(
                line.strip().startswith(tag) for line in text.splitlines()
            ):
                problems.append(f"{record.name}: spec has no {tag[:-1]}")
    return problems


CHECKS = {
    "provenance": check_provenance,
    "locks": check_locks,
    "buildroot": check_buildroot,
    "contract": check_contract,
    "specs": check_spec_sanity,
    "changelog": check_changelog_dates,
    "dependencies": check_dependencies,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--check",
        action="append",
        default=None,
        choices=sorted(CHECKS),
        help="run only these checks; repeatable",
    )
    args = parser.parse_args()

    root = factory_root(args.root)
    selected = args.check or sorted(CHECKS)
    failed = False

    for name in selected:
        problems = CHECKS[name](root)
        if problems:
            failed = True
            print(f"{name}: {len(problems)} problem(s)", file=sys.stderr)
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
        else:
            print(f"{name}: ok")

    if not failed:
        print(f"validated {len(inventory(root))} recipes")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())