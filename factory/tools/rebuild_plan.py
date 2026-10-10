#!/usr/bin/env python3
"""Decide what this run should build.

Two things are read, and the difference matters:

* A **plan** -- the wave structure from real BuildRequires. Always solved, so
  the ordering is never hand-maintained.
* A **witness** -- the published image's label, recording the input digest of
  every build it contains.

A package is selected when its input digest differs from the one the witness
records, or when the witness has never seen it. That is what makes a rerun
incremental: changing one spec selects that package and its direct
BuildRequires dependents, and leaves the other 70 alone.

Selecting from a git diff instead would be wrong the moment two runs queue --
the second push's diff says nothing about what the first run built. Selecting
from NEVR alone would miss a patch change that does not move the release.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.build_graph import reverse_dependencies
from tools.inventory import factory_root, inventory, recipe_files

LABEL = "org.projectbluefin.factory.state"


def input_digest(record, root: Path) -> str:
    """Hash everything that decides what this package builds.

    The recipe files, the recipe's source-lock entry, and the build root pin.
    Deliberately *not* the build root's resolved NEVR list: that moves
    constantly, and including it would select the whole factory every time a
    single base package is rebuilt upstream.
    """
    hasher = hashlib.sha256()
    for path in recipe_files(record):
        hasher.update(path.name.encode())
        hasher.update(path.read_bytes())
    hasher.update(json.dumps(record.lock, sort_keys=True).encode())
    # Read through buildroot_config rather than opening the file directly: a
    # wrong path here is silent. The build root would simply stop contributing
    # to the digest, and moving it would stop selecting anything to rebuild.
    from tools.buildroot import buildroot_config

    try:
        hasher.update(json.dumps(buildroot_config(root), sort_keys=True).encode())
    except ValueError:
        # validate.py is what reports a missing or malformed build root; this
        # must not be the place that fails first, or the selection silently
        # omits a build-root change.
        pass
    return hasher.hexdigest()[:32]


def read_witness(path: Path | None) -> dict[str, str]:
    """Read the published image's state label. Absent witness means nothing is known."""
    if path is None or not path.is_file():
        return {}
    text = path.read_text().strip()
    if not text or text == "null":
        return {}
    document = json.loads(text)
    if not isinstance(document, dict):
        return {}
    return document


def select(
    root: Path,
    witness: dict[str, str],
    edges: dict[str, list[str]] | None,
    only: list[str] | None = None,
    full: bool = False,
) -> dict:
    """Return the selection, the waves, and why each package was chosen."""
    records = inventory(root)
    names = [record.name for record in records]
    digests = {record.name: input_digest(record, root) for record in records}

    # A recipe whose sources the factory cannot supply is excluded here, with
    # the reason carried into the report. Selecting it would build a package
    # that fails in rpmbuild on a missing archive, and the failure would name
    # the archive rather than the lock that could not provide it.
    blocked = {
        record.name: record.blocked_reason
        for record in records
        if record.blocked
    }
    buildable = [name for name in names if name not in blocked]
    if only:
        unknown = set(only) - set(names)
        if unknown:
            raise ValueError("unknown recipes: " + ", ".join(sorted(unknown)))

    reasons: dict[str, str] = {}
    for record in records:
        name = record.name
        if name in blocked:
            continue
        if only and name not in only:
            continue
        previous = witness.get(name)
        if only or full or previous is None:
            reasons[name] = "no published build" if previous is None else "full build requested"
        elif previous != digests[name]:
            reasons[name] = "inputs changed since the last published build"

    # Drag along direct dependents of anything that changed. A library whose
    # soname moved must not leave its consumers linked against the copy it
    # replaces, so this is not an optimisation -- it is correctness.
    dependents_added = []
    if edges and reasons:
        reverse = reverse_dependencies(
            {package: set(values) for package, values in edges.items()}, buildable
        )
        changed = list(reasons)
        while changed:
            current = changed.pop()
            for dependent in sorted(reverse.get(current, set())):
                if dependent in reasons or dependent in blocked:
                    continue
                reasons[dependent] = f"BuildRequires {current}, which is being rebuilt"
                dependents_added.append(dependent)
                changed.append(dependent)

    selection = sorted(reasons)
    return {
        "build_list": selection,
        "digests": digests,
        "reasons": reasons,
        "dependents_added": sorted(dependents_added),
        "blocked": blocked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--witness", type=Path, default=None, help="path to the state label JSON")
    parser.add_argument("--edges", type=Path, default=None, help="plan JSON from build_graph.py")
    parser.add_argument("--package", action="append", default=None)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root = factory_root(args.root)
    witness = read_witness(args.witness)
    edges = None
    if args.edges and args.edges.is_file():
        edges = json.loads(args.edges.read_text()).get("edges")

    result = select(root, witness, edges, args.package, args.full)

    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
        total = len(inventory(root))
        print(f"selected {len(result['build_list'])} of {total} recipes")
        for name in result["build_list"]:
            print(f"  {name}: {result['reasons'][name]}")
        if result["blocked"]:
            print(f"  {len(result['blocked'])} recipe(s) excluded as unbuildable:")
            for name, reason in sorted(result["blocked"].items()):
                print(f"  {name}: {reason}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
