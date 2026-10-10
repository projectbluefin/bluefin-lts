#!/usr/bin/env python3
"""Tell Packit to use the factory's already-verified Source0.

Packit's ``create-archive`` action must print the path of an archive to upload.
Left alone, Packit downloads the spec's ``Source0`` URL itself, which is
exactly what this factory forbids: the whole point of the source lock is that a
build never reaches the network for its payload, and that every byte is
checked against a recorded digest before a compiler sees it.

So this prints the path of the archive that ``tools/source_pipeline.py``
already fetched and verified. If it is not staged, that is an error, not a cue
to download it here.
"""

from __future__ import annotations

import gzip
import os
import subprocess
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventory import factory_root, inventory


def _repository_root() -> Path:
    return Path(
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    )


def locate_spec(repository_root: Path, spec_path: str) -> tuple[Path, str]:
    """Find the recipe a Packit spec path refers to.

    Packit runs with the working directory set somewhere inside the
    repository, so the configured path is relative to an unknown base. Rather
    than guessing a base, the spec filename is matched against the inventory,
    which is unambiguous: recipe directories are named after their package.
    """
    configured = Path(spec_path)
    direct = repository_root / configured
    if direct.is_file():
        # Already an absolute or repo-relative path to a real spec.
        for record in inventory(factory_root(repository_root / "factory")):
            if record.spec.resolve() == direct.resolve():
                return record.directory, record.name
        return direct.parent, direct.parent.name

    candidates = [
        record
        for record in inventory(factory_root(repository_root / "factory"))
        if record.spec.name == configured.name
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"cannot uniquely locate spec {spec_path!r}: "
            f"{len(candidates)} recipes have a spec named {configured.name}"
        )
    return candidates[0].directory, candidates[0].name


def verified_source0(package: str | None = None) -> str:
    """Return the path of the staged, verified Source0 archive."""
    repository_root = _repository_root()
    factory = factory_root(repository_root / "factory")

    spec_path = os.environ.get("PACKIT_SPECFILE_PATH")
    if package is None:
        package = os.environ.get("PACKAGE")

    if package is None:
        if not spec_path:
            raise ValueError("neither PACKAGE nor PACKIT_SPECFILE_PATH is set")
        _, package = locate_spec(repository_root, spec_path)

    matches = [record for record in inventory(factory) if record.name == package]
    if len(matches) != 1:
        raise ValueError(f"{package}: not a recipe in this factory")
    record = matches[0]

    if record.no_upstream_source:
        return str(placeholder_archive(record.directory, package, record.version))

    filename = record.filename
    if not filename:
        raise ValueError(f"{package}: source lock has no filename")
    archive = record.directory / filename
    if not archive.is_file():
        raise ValueError(
            f"{package}: verified Source0 is not staged at {archive}. "
            f"Run tools/source_pipeline.py stage {package} first."
        )

    # Packit resolves the printed path relative to its own working directory,
    # so it has to be one Packit will find. A repo-relative path is correct
    # whenever Packit runs from the repository root; from anywhere else, fall
    # back to the path relative to the working directory, and if even that is
    # outside it, use the absolute path and let Packit copy the file.
    try:
        relative = archive.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        return str(archive.resolve())
    return str(relative)


def placeholder_archive(directory: Path, package: str, version: str) -> str:
    """Satisfy Packit's create-archive contract for a recipe with no archive.

    Packit calls ``create-archive`` unconditionally and raises "No output from
    create-archive action" when it gets nothing back, and there is no way to
    opt out. A recipe with no upstream payload -- a configuration-only package
    like gnome50-el10-compat, which ships one PAM file -- still has to answer.

    Nothing consumes the bytes. The build runs ``rpmbuild -br`` then ``-ba``
    with ``--no-network`` and the spec has no ``Source`` line, so the archive
    never enters the SRPM. It is written empty with a zeroed gzip header so
    two runs produce identical bytes and do not invalidate a build cache.
    """
    version = version or "0"
    archive = directory / f"{package}-{version}.tar.gz"
    if not archive.is_file():
        with archive.open("wb") as sink:
            with gzip.GzipFile(filename="", mode="wb", fileobj=sink, mtime=0) as raw:
                with tarfile.open(fileobj=raw, mode="w"):
                    pass
    return archive.name


def main() -> int:
    try:
        print(verified_source0())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())