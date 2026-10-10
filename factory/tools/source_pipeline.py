#!/usr/bin/env python3
"""Fetch and verify the upstream source for each recipe, before any build.

The factory's contract is that a build never downloads anything. A recipe's
Source0 is fetched here, verified against a digest recorded in
``config/upstream-sources.json``, and staged beside the spec. A package whose
lock is missing is not eligible for a build: this exits non-zero rather than
falling back to whatever the build root happens to serve.
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

from tools.inventory import Record, factory_root, inventory

# Archive extensions a spec's Source0 can plausibly be. Anything else (a bare
# tarball with no suffix, a directory) is a lock the operator has to stage.
ARCHIVE_SUFFIXES = (".tar.gz", ".tar.xz", ".tar.bz2", ".tar.zst", ".tar.lz", ".tar.lzma", ".tgz")


def _fetch(url: str, timeout: int = 300) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "bluefin-factory/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _digest(blob: bytes, algorithm: str) -> str:
    return hashlib.new(algorithm, blob).hexdigest()


def fetch_source(record: Record, root: Path, allow_missing: bool = False) -> Path | None:
    """Fetch, verify and stage one recipe's Source0. Returns its path.

    The primary URL is fetched directly from upstream. ``fallback_urls`` exist
    because a build must not be blocked by one host being down, but they are
    only tried after the primary fails -- and every one of them is verified
    against the same recorded digest, so a fallback cannot substitute different
    bytes.
    """
    root = factory_root(root)
    lock = record.lock
    if not lock:
        if allow_missing:
            return None
        raise ValueError(f"{record.name}: no entry in config/upstream-sources.json")

    if lock.get("no_upstream_source"):
        return None

    filename = lock.get("filename") or ""
    if not filename:
        raise ValueError(f"{record.name}: lock has no filename")
    if not filename.endswith(ARCHIVE_SUFFIXES):
        raise ValueError(
            f"{record.name}: {filename} is not a recognised source archive "
            f"(expected one of {', '.join(ARCHIVE_SUFFIXES)})"
        )

    algorithm = lock.get("checksum_type", "sha512")
    expected = lock.get("sha512") or lock.get("sha256")
    if not expected:
        raise ValueError(f"{record.name}: lock has no sha512 or sha256")

    urls = [lock["url"], *lock.get("fallback_urls", [])]
    failures = []
    for url in urls:
        try:
            blob = _fetch(url)
        except OSError as error:
            failures.append(f"{url}: {error}")
            continue
        actual = _digest(blob, algorithm)
        if actual != expected:
            failures.append(f"{url}: {algorithm} mismatch (got {actual})")
            continue

        staged = record.directory / filename
        staged.write_bytes(blob)
        return staged

    raise ValueError(f"{record.name}: no source verified\n  " + "\n  ".join(failures))


def stage(package: str, root: Path | None, output: Path | None = None) -> int:
    """Fetch one named package's source."""
    root = factory_root(root)
    matches = [record for record in inventory(root) if record.name == package]
    if not matches:
        raise ValueError(f"{package} is not a recipe in this factory")
    staged = fetch_source(matches[0], root)
    if output is not None and staged is not None:
        output.mkdir(parents=True, exist_ok=True)
        (output / staged.name).write_bytes(staged.read_bytes())
    if staged is None:
        print(f"{package}: no upstream source by policy")
    else:
        print(f"{package}: staged {staged}")
    return 0


def stage_all(root: Path | None = None) -> int:
    """Fetch every recipe's source. Reports all failures, not just the first."""
    root = factory_root(root)
    failures = []
    for record in inventory(root):
        try:
            staged = fetch_source(record, root)
        except (OSError, ValueError) as error:
            failures.append(f"{record.name}: {error}")
            continue
        print(f"staged {record.name}" if staged else f"{record.name}: no upstream source")
    if failures:
        print("\nfailures:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    return 0


def verify_staged(root: Path | None = None, package: str | None = None) -> int:
    """Re-verify already-staged sources without downloading anything.

    This runs inside the build container, after the source was fetched, so a
    source that was swapped between staging and build fails here rather than
    producing an RPM from bytes nobody verified.
    """
    root = factory_root(root)
    failures = []
    checked = 0
    for record in inventory(root):
        if package and record.name != package:
            continue
        lock = record.lock
        if lock.get("no_upstream_source"):
            continue
        filename = lock.get("filename") or ""
        staged = record.directory / filename
        if not filename or not staged.is_file():
            failures.append(f"{record.name}: {filename or '(no filename)'} is not staged")
            continue
        algorithm = lock.get("checksum_type", "sha512")
        expected = lock.get("sha512") or lock.get("sha256")
        actual = _digest(staged.read_bytes(), algorithm)
        checked += 1
        if actual != expected:
            failures.append(f"{record.name}: {filename} fails {algorithm} verification")

    if failures:
        print("staged source verification failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print(f"verified {checked} staged sources")
    return 0


def report(root: Path | None = None) -> int:
    """Print the resolved source for every recipe."""
    root = factory_root(root)
    rows = []
    for record in inventory(root):
        lock = record.lock
        if not lock:
            rows.append((record.name, "UNLOCKED", "-"))
        elif lock.get("no_upstream_source"):
            rows.append((record.name, "no-upstream-source", lock.get("version", "")))
        else:
            rows.append((record.name, lock.get("version", "?"), lock.get("url", "")))
    width = max(len(row[0]) for row in rows) if rows else 10
    for name, version, url in rows:
        print(f"{name:<{width}}  {version:<24}  {url}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage_parser = subparsers.add_parser("stage")
    stage_parser.add_argument("package")
    stage_parser.add_argument("--root", type=Path, default=None)
    stage_parser.add_argument("--output", type=Path, default=None)

    all_parser = subparsers.add_parser("stage-all")
    all_parser.add_argument("--root", type=Path, default=None)

    verify_parser = subparsers.add_parser("verify-staged")
    verify_parser.add_argument("--root", type=Path, default=None)
    verify_parser.add_argument("--package", default=None)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--root", type=Path, default=None)

    args = parser.parse_args()
    try:
        if args.command == "stage":
            return stage(args.package, args.root, args.output)
        if args.command == "stage-all":
            return stage_all(args.root)
        if args.command == "verify-staged":
            return verify_staged(args.root, args.package)
        if args.command == "report":
            return report(args.root)
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())