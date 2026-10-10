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


# Adapted from utah-packages: preserve capability namespaces.
CAPABILITY = re.compile(r"[^\s()<>=!,]+(?:\([^()]*\))?")


def _requirement_names(requirement: str) -> list[str]:
    rich = requirement.strip().startswith("(")
    if rich:
        tokens = CAPABILITY.findall(requirement.strip()[1:-1])
        return [token for token in tokens if token not in
                {"and", "or", "with", "without", "if", "else", "unless"}
                and not re.match(r"^[0-9%]", token)]
    match = CAPABILITY.match(requirement.strip())
    return [match.group(0)] if match else []


def resolve_edges(
    rows: dict[str, set[str]],
    factory_packages: set[str],
    provided: dict[str, set[str]] | None = None,
) -> dict[str, set[str]]:
    """Resolve capabilities through subpackage names and RPM provides."""
    providers: dict[str, set[str]] = defaultdict(set)
    for package in factory_packages:
        providers[package].add(package)
    for package, capabilities in (provided or {}).items():
        if package in factory_packages:
            for capability in capabilities:
                providers[capability].add(package)
    edges: dict[str, set[str]] = defaultdict(set)
    for package, requirements in rows.items():
        if package not in factory_packages:
            continue
        for requirement in requirements:
            for capability in _requirement_names(requirement):
                edges[package].update(providers.get(capability, set()) - {package})
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
        if package not in indegree:
            continue
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


def bootstrap_edges(edges, rows, names, provided, satisfied):
    """Break only cyclic edges whose exact requirements have base witnesses.

    Adapted from Utah's cycle detection, with CentOS RPM version constraints
    replacing declared stages. Preserve the full graph for rebuild selection.
    """
    scheduling = {name: set(edges.get(name, set())) & names for name in names}
    witnesses = []

    def reachable(start, target):
        pending, visited = [start], set()
        while pending:
            node = pending.pop()
            if node == target:
                return True
            if node not in visited:
                visited.add(node)
                pending.extend(scheduling.get(node, set()) - visited)
        return False

    for consumer in sorted(names):
        for provider in sorted(scheduling[consumer]):
            if not reachable(provider, consumer):
                continue
            requirements = [requirement for requirement in rows[consumer]
                            if provider in resolve_edges(
                                {consumer: {requirement}}, names, provided).get(consumer, set())]
            available = satisfied.get(consumer, {})
            if requirements and all(available.get(req) for req in requirements):
                scheduling[consumer].remove(provider)
                witnesses.append({"consumer": consumer, "provider": provider,
                                  "requirements": {req: available[req]
                                                   for req in sorted(requirements)}})
    return scheduling, witnesses


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


def plan(root: Path | None = None, rows_dir: Path | None = None,
         selected: list[str] | None = None, graph_only: bool = False) -> dict:
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
            queried = rows_dir / f"{record.name}.br"
            rows[record.name] = (set(queried.read_text().splitlines()) if queried.is_file()
                                 else set(re.findall(
                                     r"^BuildRequires(?:[0-9]*)?:\s*(.+)$", text, re.MULTILINE)))
    names = [record.name for record in inventory(root)]
    provided: dict[str, set[str]] = defaultdict(set)
    if rows_dir is not None:
        for record in inventory(root):
            for suffix in ("names", "provides"):
                path = rows_dir / f"{record.name}.{suffix}"
                if path.is_file():
                    for line in path.read_text().splitlines():
                        provided[record.name].update(_requirement_names(line))
        base = rows_dir / "base-providers.json"
        if base.is_file():
            for package, capabilities in json.loads(base.read_text()).items():
                provided[package].update(capabilities)
    edges = resolve_edges(rows, set(names), provided)
    result = {
        "packages": sorted(names),
        "edges": {package: sorted(values) for package, values in sorted(edges.items())},
    }
    if not graph_only:
        building = names if selected is None else selected
        unknown = set(building) - set(names)
        if unknown:
            raise ValueError("unknown recipes: " + ", ".join(sorted(unknown)))
        satisfied_path = rows_dir / "base-satisfied.json" if rows_dir is not None else None
        satisfied = (json.loads(satisfied_path.read_text())
                     if satisfied_path is not None and satisfied_path.is_file() else {})
        scheduling, witnesses = bootstrap_edges(edges, rows, set(building), provided, satisfied)
        result["bootstrap"] = witnesses
        result["waves"] = waves(scheduling, building)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--root", type=Path, default=None)
    plan_parser.add_argument("--rows", type=Path, default=None)
    plan_parser.add_argument("--output", type=Path, default=None)
    plan_parser.add_argument("--packages", help="JSON array of the selected build set")
    plan_parser.add_argument("--graph-only", action="store_true")

    reverse_parser = subparsers.add_parser("reverse-deps")
    reverse_parser.add_argument("package")
    reverse_parser.add_argument("--root", type=Path, default=None)
    reverse_parser.add_argument("--rows", type=Path, default=None)

    args = parser.parse_args()
    try:
        if args.command == "plan":
            selected = json.loads(args.packages) if args.packages is not None else None
            result = plan(args.root, args.rows, selected, args.graph_only)
            rendered = json.dumps(result, indent=2)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(rendered + "\n")
                depth = len(result.get("waves", []))
                print(f"{len(result['packages'])} recipes; {depth} selected waves -> {args.output}")
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
