#!/usr/bin/env python3
"""Decide what a publish may ship, and report what a run failed to build.

Two responsibilities that belong together because they answer the same
question from opposite ends: what went in, and what did not.

The publish decision is a transaction, not a tag move. A candidate repository
is only published if the packages the image actually installs resolve against
it plus the pinned c10s base -- if a library moved its soname and a consumer
was not rebuilt, the transaction fails and the tag does not move, however many
other packages built. That is the gate protecting the image.

The report exists because a run that publishes nothing still needs to say
which package stopped it, and because a failed package must keep its previous
build rather than disappear from the repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ARTIFACT_PREFIX = "factory-rpm-s"


def artifact_for(package: str) -> str:
    return f"{ARTIFACT_PREFIX}{package}"


def did_build(built: set[str], package: str) -> bool:
    return artifact_for(package) in built


def failed_packages(build_list: list[str], artifacts: set[str]) -> list[str]:
    """Every selected package that produced no RPM artifact this run."""
    return [package for package in build_list if not did_build(artifacts, package)]


def publish_allowed(failures: list[str], transaction_ok: bool) -> tuple[bool, str]:
    """Decide whether the tag may move.

    A build failure alone does not block publication. Incremental publication
    is the whole point of the state label: if one package of seventy fails, the
    other sixty-nine should still reach consumers rather than being held back
    until the flaky one is fixed. Holding everything is how three builds in
    four weeks used to publish.

    What does block is the transaction: a candidate the image cannot install
    is not publishable at all, however many packages built.
    """
    if not transaction_ok:
        return False, "the consumer transaction does not resolve against the candidate"
    if failures:
        return True, (
            f"publishing {len(failures)} package(s) that failed this run; "
            "each keeps its previous build or stays absent"
        )
    return True, "every selected package built"


def render_report(
    build_list: list[str],
    failures: list[str],
    run_url: str,
    reasons: dict[str, str] | None = None,
) -> str:
    reasons = reasons or {}
    lines = ["# Factory build report", ""]
    if not build_list:
        lines += ["No packages were selected.", ""]
        return "\n".join(lines)

    built = [package for package in build_list if package not in failures]

    lines += [f"Selected {len(build_list)} package(s).", ""]
    if failures:
        lines += [f"## Did not build ({len(failures)})", ""]
        for package in failures:
            reason = reasons.get(package)
            suffix = f" — {reason}" if reason else ""
            lines.append(f"- `{package}`{suffix}")
        lines.append("")
        # The successes are listed too. A report that names only what failed
        # cannot answer "did the package I changed get built?", which is the
        # first question anyone reads a build report with.
        lines += [f"## Built ({len(built)})", ""]
        for package in built:
            lines.append(f"- `{package}`")
        lines.append("")
        lines += [
            f"{len(built)} package(s) still publish; a failed package keeps its "
            "previous build rather than being dropped.",
            "",
        ]
    else:
        for package in built:
            lines.append(f"- `{package}`")
        lines.append("")
        lines += ["Every selected package built.", ""]

    lines.append(f"Run: {run_url}")
    lines.append("")
    return "\n".join(lines)


def marker(text: str) -> str:
    """Extract the failure set from a previously posted report body."""
    start = text.find("<!-- factory-failures:")
    if start < 0:
        return ""
    end = text.find("-->", start)
    return text[start + len("<!-- factory-failures:") : end].strip()


def with_marker(text: str, failures: list[str]) -> str:
    payload = f"<!-- factory-failures:{json.dumps(failures)} -->\n"
    return payload + text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--build-list", required=True)
    report_parser.add_argument("--artifacts", type=Path, required=True)
    report_parser.add_argument("--run-url", default="")
    report_parser.add_argument("--reasons", type=Path, default=None)
    report_parser.add_argument("--output", type=Path, required=True)
    report_parser.add_argument("--failed-output", type=Path, required=True)

    decide_parser = subparsers.add_parser("decide")
    decide_parser.add_argument("--failures", required=True, help="JSON array of names")
    decide_parser.add_argument("--transaction-ok", default="true")

    marker_parser = subparsers.add_parser("marker")
    marker_parser.add_argument("body", nargs="?", type=Path)

    args = parser.parse_args()

    if args.command == "report":
        build_list = json.loads(args.build_list)
        artifacts = set(json.loads(args.artifacts.read_text()))
        reasons = {}
        if args.reasons and args.reasons.is_file():
            reasons = json.loads(args.reasons.read_text()).get("reasons", {})
        failures = failed_packages(build_list, artifacts)
        args.output.write_text(
            with_marker(
                render_report(build_list, failures, args.run_url, reasons),
                failures,
            )
        )
        args.failed_output.write_text(json.dumps(failures, indent=2) + "\n")
        for package in failures:
            print(f"did not build: {package}", file=sys.stderr)
        return 0

    if args.command == "decide":
        failures = json.loads(args.failures)
        allowed, reason = publish_allowed(failures, args.transaction_ok == "true")
        print(json.dumps({"publish": allowed, "reason": reason}, indent=2))
        return 0

    if args.command == "marker":
        body = args.body.read_text() if args.body else ""
        print(marker(body))
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
