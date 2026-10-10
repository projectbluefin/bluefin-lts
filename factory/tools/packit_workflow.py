#!/usr/bin/env python3
"""Machine-readable helpers shared by the Packit SRPM workflow.

Kept separate from the workflow YAML so the package list, the matrix chunking
and the result format are all testable without running an action.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventory import inventory

# GitHub expands a matrix larger than 256 jobs to nothing rather than failing,
# so a workflow over the cap runs zero jobs and reports success. Every fan-out
# in this repository therefore hands out chunks rather than one list.
MATRIX_CHUNK = 200


def package_names(root: Path | None = None) -> list[str]:
    return [record.name for record in inventory(root) if not record.blocked]


def package_chunks(names: list[str], size: int = MATRIX_CHUNK) -> list[str]:
    """Split names into JSON-encoded chunks, none exceeding the matrix cap."""
    if size < 1:
        raise ValueError("chunk size must be positive")
    return [
        json.dumps(names[start : start + size])
        for start in range(0, len(names), size)
    ]


def result(package: str, status: str, nevra: str = "") -> str:
    return json.dumps(
        {"package": package, "status": status, "nevra": nevra},
        sort_keys=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    packages_parser = subparsers.add_parser("packages")
    packages_parser.add_argument("--root", type=Path, default=None)

    chunks_parser = subparsers.add_parser("chunks")
    chunks_parser.add_argument("--root", type=Path, default=None)
    chunks_parser.add_argument("--size", type=int, default=MATRIX_CHUNK)

    result_parser = subparsers.add_parser("result")
    result_parser.add_argument("--package", required=True)
    result_parser.add_argument("--status", choices=("success", "failure"), required=True)
    result_parser.add_argument("--nevra", default="")

    args = parser.parse_args()
    if args.command == "packages":
        print(json.dumps(package_names(args.root)))
    elif args.command == "chunks":
        print(json.dumps(package_chunks(package_names(args.root), args.size)))
    elif args.command == "result":
        print(result(args.package, args.status, args.nevra))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
