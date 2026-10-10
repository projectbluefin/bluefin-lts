#!/usr/bin/env python3
"""Prepare the buildroot image exactly once for a whole run.

``config/buildroot.json`` names the image every RPM is built against, and is
the single source of truth for it. The image is pulled once here, resolved to
a digest, recorded, and saved as a single artifact every build job in the run
loads from disk.

JSON rather than YAML, and the standard library rather than PyYAML: this tool
runs on CI runners that do not have third-party Python packages installed, and
a tool that only works on the machine that wrote it is not a tool.

Why not have each job pull the pin itself:

* The digest can die between the run starting and a later job starting. That
  is not hypothetical -- the base image is republished several times a day and
  each superseded digest is garbage collected, so a pin correct at 06:01 was a
  404 by 07:13 the same morning. Every job in that wave died on exit 125.
* Every job then provably uses the same bytes, which is a stronger
  reproducibility claim than a pin can make on its own.
* On a 14 GB runner disk it replaces several hundred GB of pulls with one
  image.

``registry_pull_per_job`` exists for environments where that disk budget makes
the hand-off impractical. It is false by default, so using it is a visible
choice rather than an accident.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventory import factory_root, inventory

MIRROR_PREFIX = "ghcr.io/projectbluefin/bluefin-lts-buildroot"


def buildroot_config(root: Path) -> dict:
    path = root / "config" / "buildroot.json"
    if not path.is_file():
        raise ValueError(f"{path} is missing; the build root must be pinned")
    try:
        document = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: {error}") from error
    if not isinstance(document, dict):
        raise ValueError(f"{path}: expected an object")
    for field in ("image", "digest"):
        if not document.get(field):
            raise ValueError(f"{path}: no {field}")
    digest = str(document["digest"])
    if not digest.startswith("sha256:") or len(digest) != 71:
        raise ValueError(
            f"{path}: digest {digest!r} is not a sha256. A tag alone is not a "
            "pin: it means building against whatever the tag resolved to."
        )
    return document


def read_pin(root: Path) -> str:
    """The pinned reference as ``image:tag@sha256:...``."""
    config = buildroot_config(root)
    return f"{config['image']}@{config['digest']}"


def split_pin(pin: str) -> tuple[str, str]:
    reference, _, digest = pin.partition("@")
    return reference, digest


def is_mirror(reference: str) -> bool:
    return reference.startswith(MIRROR_PREFIX)


def resolve(pin: str, engine: str = "docker") -> dict:
    """Pull the build root and report what it resolved to."""
    reference, expected = split_pin(pin)
    pull = subprocess.run([engine, "pull", reference], capture_output=True, text=True)
    resolved = subprocess.run(
        [engine, "image", "inspect", reference, "--format", "{{index .RepoDigests 0}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    actual = resolved.stdout.strip().rpartition("@")[2] if resolved.returncode == 0 else ""

    result = {
        "expected": expected,
        "actual": actual,
        "reference": reference,
        "pulled": pull.returncode == 0,
        "mirrored": is_mirror(reference),
        "matches": actual == expected,
    }

    if result["mirrored"]:
        # A mirror is never pruned, so a missing digest cannot be explained by
        # expiry and must fail the run rather than be reported and continued.
        if not result["pulled"] or not result["matches"]:
            raise SystemExit(
                f"build root mirror {reference} does not resolve to the pinned digest.\n"
                f"  expected: {expected}\n"
                f"  actual:   {actual or '(not pulled)'}\n"
                "A mirror digest cannot rot, so this is a real problem."
            )
    else:
        if not result["pulled"]:
            raise SystemExit(f"could not pull {reference}")
        if not result["matches"]:
            # The upstream tag moved. Reported, not fatal: failing on it
            # recreates the outage the artifact hand-off exists to prevent.
            print(
                f"::warning title=build root moved::{reference} now resolves to "
                f"{actual or '(unknown)'}, not the recorded {expected}. Continuing "
                "on what it resolved to.",
                file=sys.stderr,
            )
    return result


def snapshot(root: Path, digest: str, output: Path) -> Path:
    """Record the build root digest and the recipe set beside the repository.

    Provenance answers what an image was built from. This records what was
    *in* it, so a consumer can tell a stale repository from an empty one.
    """
    config = buildroot_config(root)
    document = {
        "schema": 1,
        "buildroot": config["image"],
        "buildroot_digest": digest,
        "buildroot_pin": read_pin(root),
        "recipes": sorted(record.name for record in inventory(root)),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--engine", default="docker")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--digest-only",
        action="store_true",
        help="print just the image reference without its digest",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="write a provenance record of the build root and recipe set",
    )
    args = parser.parse_args()

    root = factory_root(args.root)
    try:
        pin = read_pin(root)
        if args.digest_only:
            print(split_pin(pin)[0])
            return 0
        result = resolve(pin, args.engine)
        print(json.dumps(result, indent=2))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n")
        if args.snapshot:
            snapshot(root, result["actual"] or result["expected"], args.snapshot)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    except subprocess.CalledProcessError as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
