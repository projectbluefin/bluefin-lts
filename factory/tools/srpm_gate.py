#!/usr/bin/env python3
"""Build one SRPM with Packit, against the factory's verified source.

This is the gate, so it is worth being precise about what it does and does not
prove.

It proves the spec is well formed: ``packit srpm`` parses the recipe, resolves
its macros, applies its patches to the staged source, and writes an SRPM. A
spec that is broken fails here in seconds.

It does **not** prove the package compiles. That needs the real build root --
the pinned c10s image -- and is the build workflow's job. An SRPM built here
says nothing about whether gnome-shell will build against EL10; it says the
recipe is not malformed.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventory import factory_root, inventory
from tools.source_pipeline import fetch_source, verify_staged

PACKIT_IMAGE = "quay.io/packit/packit"


def command(package: str, record, output: Path, root: Path, image: str, engine: str = "docker") -> list[str]:
    """Build the docker invocation. Separated so the paths can be tested.

    Every host path in a ``-v`` must be absolute. Docker reads a relative one
    as a *volume name* and rejects it: ``create work/srpm: "work/srpm"
    includes invalid characters for a local volume name``. The error names the
    path and nothing about the fix.

    A missing host path is worse than an invalid one: docker silently creates
    it as an empty named volume, and the build runs against nothing. Both are
    avoided by resolving the paths and checking the sources exist.
    """
    out_dir = output.parent.resolve()
    repo_dir = root.parent.resolve()

    if not out_dir.is_dir():
        raise ValueError(f"output directory does not exist: {out_dir}")

    return [
        engine, "run", "--rm",
        "-e", f"PACKAGE={package}",
        "-e", f"OUTPUT_NAME={output.name}",
        "-e", "PACKIT_SPECFILE_PATH=" + str(record.spec.relative_to(root.parent)),
        "-v", f"{repo_dir}:/repo:Z",
        "-v", f"{out_dir}:/out:Z",
        "-w", "/repo",
        image,
        "bash", "-exc",
        (
            'git config --global --add safe.directory "*"; '
            'packit srpm --preserve-spec --output "/out/$OUTPUT_NAME" -p "$PACKAGE"; '
            'rpm -qp --qf "%{NAME}-%{VERSION}-%{RELEASE}\\n" "/out/$OUTPUT_NAME"'
        ),
    ]


def build(package: str, output: Path, root: Path | None, image: str, engine: str = "docker") -> int:
    root = factory_root(root)
    matches = [record for record in inventory(root) if record.name == package]
    if not matches:
        print(f"{package} is not a recipe in this factory", file=sys.stderr)
        return 1
    record = matches[0]

    # Refuse here, with the reason, rather than letting rpmbuild fail on a
    # missing archive. `rpmbuild -bs` reports "Bad file:
    # .../glycin-2.0.8-vendor.tar.xz: No such file or directory", which names
    # the archive and not the reason the factory cannot produce it.
    if record.blocked:
        print(
            f"{package}: not buildable by this factory.\n"
            f"  {record.blocked_reason}",
            file=sys.stderr,
        )
        return 1

    # Resolve before anything else: the caller may pass a relative --output,
    # and a relative path reaches docker as a volume name.
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    # Stage the verified source first. packit_source0.py will refuse to print
    # a path for an archive that is not there, which is the behaviour we want:
    # the gate must not be able to quietly download an unverified payload.
    try:
        fetch_source(record, root)
    except (OSError, ValueError) as error:
        print(f"{package}: {error}", file=sys.stderr)
        return 1

    if verify_staged(root, package) != 0:
        return 1

    try:
        argv = command(package, record, output, root, image, engine)
    except ValueError as error:
        print(f"{package}: {error}", file=sys.stderr)
        return 1

    output.unlink(missing_ok=True)
    result = subprocess.run(argv, check=False)
    if result.returncode != 0:
        print(f"{package}: packit srpm failed", file=sys.stderr)
        return result.returncode

    produced = output
    # An upload with no matching file cannot be trusted to fail the job on
    # its own, so the presence of the artifact is checked explicitly.
    if not produced.is_file() or produced.stat().st_size == 0:
        print(f"{package}: packit reported success but produced no SRPM", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--engine", choices=("docker", "podman"), default="docker")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--image",
        default=f"{PACKIT_IMAGE}:latest",
        help="Packit container image; pin by digest in CI",
    )
    args = parser.parse_args()
    return build(args.package, args.output, args.root, args.image, args.engine)


if __name__ == "__main__":
    raise SystemExit(main())
