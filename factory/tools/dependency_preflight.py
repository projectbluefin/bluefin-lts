#!/usr/bin/env python3
"""Check declared GNOME build dependencies before starting any compilation.

Version comparisons run with RPM in the pinned CentOS extractor. Capabilities
generated from payloads can establish names, but cannot establish versions;
recipes must declare versioned Provides when those versions are needed.
This checks declarations and ordering, not source/API compatibility or the
joint installability of the eventual RPM payloads.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.build_graph import _requirement_names, plan
from tools.inventory import factory_root

DEPENDENCY = re.compile(r"^(\S+?)(?:\s+([<>=]+)\s+(\S+))?$")


def rpm_matches(provide: str, requirement: str, rpm) -> bool:
    """Use RPM's range comparison, including epochs and prerelease ordering."""
    # rpmdsCompare treats an unversioned provide as an overlapping wildcard.
    # That does not establish the version this preflight is meant to verify.
    offered = DEPENDENCY.fullmatch(provide)
    needed = DEPENDENCY.fullmatch(requirement)
    if offered and needed and needed.group(2) and not offered.group(2):
        return False

    def dependency(text, tag):
        match = DEPENDENCY.fullmatch(text)
        if not match:
            raise ValueError(f"unsupported dependency: {text}")
        name, operator, version = match.groups()
        flags = 0
        for symbol in operator or "":
            flags |= {"<": rpm.RPMSENSE_LESS, ">": rpm.RPMSENSE_GREATER,
                      "=": rpm.RPMSENSE_EQUAL}[symbol]
        return rpm.ds((name, flags, version or ""), tag)

    return dependency(provide, rpm.RPMTAG_PROVIDENAME).Compare(
        dependency(requirement, rpm.RPMTAG_REQUIRENAME))


def write_factory_witnesses(rows: Path, matches) -> None:
    """Called inside CentOS, using exact spec Provides and base source aliases."""
    declared = {path.stem: path.read_text().splitlines()
                for path in rows.glob("*.provides")}
    implicit = json.loads((rows / "base-providers.json").read_text())
    result = {}
    for path in sorted(rows.glob("*.br")):
        requirements = {}
        for requirement in path.read_text().splitlines():
            matched, unknown = [], []
            names = _requirement_names(requirement)
            if requirement.startswith("("):
                requirements[requirement] = {"matched": [], "unverified": []}
                continue
            for provider, capabilities in declared.items():
                explicit = [cap for cap in capabilities
                            if _requirement_names(cap) == names]
                if any(matches(cap, requirement) for cap in explicit):
                    matched.append(provider)
                elif not explicit and names and names[0] in implicit.get(provider, []):
                    if DEPENDENCY.fullmatch(requirement).group(2):
                        unknown.append(provider)
                    else:
                        matched.append(provider)
            requirements[requirement] = {"matched": sorted(matched),
                                         "unverified": sorted(unknown)}
        result[path.stem] = requirements
    (rows / "factory-satisfied.json").write_text(json.dumps(result, indent=2) + "\n")


def check(root: Path, rows: Path, candidate: dict) -> dict:
    """Replay the real plan, then require a witness for every selected BR."""
    expected = plan(root, rows, stack=True)
    if candidate != expected:
        raise ValueError("dependency plan differs from the current CentOS rows/targets")
    position = {name: wave for wave, names in enumerate(candidate["waves"]) for name in names}
    base = json.loads((rows / "base-satisfied.json").read_text())
    factory = json.loads((rows / "factory-satisfied.json").read_text())
    checked, errors = [], []
    for consumer in sorted(position):
        for requirement in (rows / f"{consumer}.br").read_text().splitlines():
            if base.get(consumer, {}).get(requirement):
                checked.append({"consumer": consumer, "requirement": requirement,
                                "base": base[consumer][requirement]})
                continue
            witnesses = factory[consumer][requirement]
            earlier = [name for name in witnesses["matched"]
                       if name in position and position[name] < position[consumer]]
            if earlier:
                checked.append({"consumer": consumer, "requirement": requirement,
                                "factory": earlier})
            else:
                detail = ("version unverified; declare versioned Provides in " +
                          ", ".join(witnesses["unverified"]) if witnesses["unverified"]
                          else "no compatible base or earlier-wave factory provider")
                errors.append(f"{consumer}: {requirement}: {detail}")
    return {"status": "failed" if errors else "passed", "recipes": len(position),
            "waves": len(candidate["waves"]), "dependencies": checked, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = check(factory_root(args.root), args.rows, json.loads(args.plan.read_text()))
    except (OSError, ValueError, KeyError) as error:
        report = {"status": "failed", "errors": [str(error)]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    for error in report["errors"]:
        print(error, file=sys.stderr)
    print(f"GNOME dependency preflight: {report['status']} -> {args.output}")
    return int(report["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
