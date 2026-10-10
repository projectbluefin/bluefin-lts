#!/usr/bin/env python3
"""Solve build order from real BuildRequires.

The factory cannot ship hand-assigned build stages. They rot: a new
BuildRequires edge is invisible until a build fails somewhere later, and a
stage that is no longer needed still serializes work. So the order is computed
from what ``rpmspec`` says the recipes actually require.

Graph extraction needs ``rpmspec``, which means it runs in the build root, not
on a developer machine. This module is split accordingly:

* ``parse_rows`` and ``waves`` are pure functions over extracted rows, and are
  what the tests exercise.
* the ``main`` entry point shells out to ``rpmspec`` to produce those rows.

A wave is one unit of build parallelism: every package in wave N can be built
concurrently, and every package in wave N+1 has all of its factory
BuildRequires satisfied by wave N.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventory import factory_root, inventory

# Rows are written by the extractor as tab-separated fields. A BuildRequires
# is kept only when it is a plain name optionally with a version constraint.
# Rich dependencies (parenthesised boolean expressions) are kept as whole
# strings: they are not decomposed here because a wrong decomposition would
# order a package wrongly, and ordering wrongly produces a build that fails
# with a confusing "not found" rather than an obvious one.
FIELD_SEP = "\t"


def parse_rows(text: str) -> dict[str, set[str]]:
    """Parse extracted ``package<TAB>requirement`` rows into an adjacency map.

    Only requirements naming a package this factory builds become edges.
    A requirement satisfied by the base image (gcc, meson, bash) is not an
    edge, because it places no constraint on our build order.
    """
    graph: dict[str, set[str]] = defaultdict(set)
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split(FIELD_SEP)
        if len(parts) != 2:
            raise ValueError(f"malformed graph row: {line!r}")
        package, requirement = parts
        graph[package].add(requirement)
    return dict(graph)


def _requirement_names(requirement: str) -> list[str]:
    """Extract candidate package names from a BuildRequires token.

    ``gtk4 >= 4.20`` names gtk4. ``(glib2 >= 2.86 with pango)`` names two, and
    an alternation names both -- either may satisfy it, so both are recorded
    as predecessors. Over-approximating here is safe: it can only make a wave
    later than strictly necessary. Under-approximating would break the build.
    """
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9+._-]*", requirement)
    ignored = {"and", "or", "without", "with", "if", "else"}
    return [token for token in tokens if token.lower() not in ignored]


def resolve_edges(
    rows: dict[str, set[str]],
    factory_packages: set[str],
) -> dict[str, set[str]]:
    """Reduce extracted rows to edges between packages this factory builds."""
    edges: dict[str, set[str]] = defaultdict(set)
    for package, requirements in rows.items():
        if package not in factory_packages:
            continue
        for requirement in requirements:
            for name in _requirement_names(requirement):
                if name in factory_packages and name != package:
                    edges[package].add(name)
    return dict(edges)


def waves(edges: dict[str, set[str]], packages: list[str]) -> list[list[str]]:
    """Topologically layer the graph. Returns waves, deepest chain last.

    Ties are broken by name so the same input always produces the same plan:
    an unstable order would make a build non-reproducible and would make a
    diff of two plans unreadable.
    """
    successors: dict[str, set[str]] = {package: set() for package in packages}
    indegree: dict[str, int] = {package: 0 for package in packages}
    for package, predecessors in edges.items():
        for predecessor in predecessors:
            if predecessor not in successors or predecessor == package:
                continue
            successors[predecessor].add(package)
            indegree[package] += 1

    ready = deque(sorted(package for package in packages if indegree[package] == 0))
    ordered: list[str] = []
    result: list[list[str]] = []

    while ready:
        wave = sorted(ready)
        result.append(wave)
        ready.clear()
        for package in wave:
            ordered.append(package)
            for successor in sorted(successors[package]):
                indegree[successor] -= 1
                if indegree[successor] == 0:
                    ready.append(successor)

    unresolved = [package for package in packages if package not in ordered]
    if unresolved:
        # A BuildRequires cycle inside one factory package set. This names the
        # members instead of dropping them, because silently omitting a
        # package from the plan is how a recipe stops being built.
        raise ValueError(
            "BuildRequires cycle among: " + ", ".join(sorted(unresolved))
        )
    return result


def reverse_dependencies(edges: dict[str, set[str]], packages: list[str]) -> dict[str, set[str]]:
    """Invert the graph: package -> everything that BuildRequires it.

    Used to drag a consumer along when its provider changes, so a library
    rebuild does not leave a consumer linked against the copy it replaced.
    """
    reverse: dict[str, set[str]] = {package: set() for package in packages}
    for package, predecessors in edges.items():
        for predecessor in predecessors:
            reverse.setdefault(predecessor, set()).add(package)
    return reverse


def extract(root: Path | None, rows_dir: Path) -> dict[str, set[str]]:
    """Run ``rpmspec --parse`` over every recipe and collect BuildRequires."""
    root = factory_root(root)
    rows_dir.mkdir(parents=True, exist_ok=True)

    for record in inventory(root):
        result = subprocess.run(
            ["rpmspec", "--parse", str(record.spec)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            # A spec that will not parse cannot contribute edges, and silently
            # skipping it would let it be scheduled into wave 0 where it
            # fails with no explanation.
            raise ValueError(f"{record.name}: rpmspec failed\n{result.stderr.strip()}")
        text = result.stdout
        (rows_dir / f"{record.name}.spec").write_text(text)

    collected: dict[str, list[str]] = defaultdict(list)
    for record in inventory(root):
        text = (rows_dir / f"{record.name}.spec").read_text()
        for match in re.finditer(r"^BuildRequires(?:[0-9]*)?:\s*(.+)$", text, re.MULTILINE):
            collected[record.name].append(match.group(1).strip())
    return {package: set(items) for package, items in collected.items()}


def plan(root: Path | None = None, rows_dir: Path | None = None) -> dict:
    """Produce the full build plan: waves plus the graph behind them."""
    root = factory_root(root)
    if rows_dir is None:
        rows = extract(root, root / "work" / "graph" / "rows")
    else:
        # The workflow already parsed these specs with the EL10 macros.
        # Re-parsing on the host discards that result and requires host RPM.
        rows = {}
        for record in inventory(root):
            text = (rows_dir / f"{record.name}.spec").read_text()
            rows[record.name] = set(re.findall(
                r"^BuildRequires(?:[0-9]*)?:\s*(.+)$", text, re.MULTILINE
            ))
    names = [record.name for record in inventory(root)]
    edges = resolve_edges(rows, set(names))
    return {
        "packages": sorted(names),
        "waves": waves(edges, names),
        "edges": {package: sorted(values) for package, values in sorted(edges.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--root", type=Path, default=None)
    plan_parser.add_argument("--rows", type=Path, default=None)
    plan_parser.add_argument("--output", type=Path, default=None)

    reverse_parser = subparsers.add_parser("reverse-deps")
    reverse_parser.add_argument("package")
    reverse_parser.add_argument("--root", type=Path, default=None)
    reverse_parser.add_argument("--rows", type=Path, default=None)

    args = parser.parse_args()
    try:
        if args.command == "plan":
            result = plan(args.root, args.rows)
            rendered = json.dumps(result, indent=2)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(rendered + "\n")
                depth = len(result["waves"])
                print(f"{len(result['packages'])} packages in {depth} waves -> {args.output}")
            else:
                print(rendered)
        elif args.command == "reverse-deps":
            result = plan(args.root, args.rows)
            names = result["packages"]
            edges = {package: set(values) for package, values in result["edges"].items()}
            reverse = reverse_dependencies(edges, names)
            print(json.dumps(sorted(reverse.get(args.package, set()))))
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
