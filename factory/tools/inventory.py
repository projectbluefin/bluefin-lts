#!/usr/bin/env python3
"""Discover factory recipes and read the source lock that governs each one.

Every recipe is a directory under ``packages/`` holding exactly one ``.spec``.
The source lock lives in ``config/upstream-sources.json`` and must cover every
recipe: a recipe with no entry has no verified Source0 and therefore cannot
build. Both directions are enforced by ``tools/validate.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = 1


def factory_root(start: Path | None = None) -> Path:
    """Return the factory directory, walking up from ``start`` if needed.

    Works whether the caller runs from the repository root, from inside
    ``factory/``, or from a test that passes an explicit path.
    """
    if start is not None:
        candidate = start.resolve()
        if (candidate / "packages").is_dir() and (candidate / "config").is_dir():
            return candidate
        raise ValueError(f"not a factory root: {candidate}")

    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "packages").is_dir() and (candidate / "config").is_dir():
            return candidate
        if (candidate / "factory" / "packages").is_dir():
            return candidate / "factory"
    raise ValueError(f"could not locate the factory root from {here}")


@dataclass
class Record:
    """One recipe: the directory, its spec, and the lock entry naming it."""

    name: str
    directory: Path
    spec: Path
    lock: dict = field(default_factory=dict)

    @property
    def upstream_name(self) -> str:
        return self.lock.get("dist_git_name", self.name)

    @property
    def version(self) -> str:
        return self.lock.get("version", "")

    @property
    def no_upstream_source(self) -> bool:
        return bool(self.lock.get("no_upstream_source"))

    @property
    def filename(self) -> str:
        return self.lock.get("filename", "")


def inventory(root: Path | None = None) -> list[Record]:
    """Return every recipe, sorted by name.

    A directory with no spec is not a recipe and is skipped; a directory with
    two specs is ambiguous and raises, because silently picking one would make
    the recipe set depend on filesystem iteration order.
    """
    root = factory_root(root)
    locks = source_locks(root)
    records: list[Record] = []

    for directory in sorted((root / "packages").iterdir()):
        if not directory.is_dir():
            continue
        specs = sorted(directory.glob("*.spec"))
        if not specs:
            continue
        if len(specs) > 1:
            raise ValueError(f"{directory.name} has multiple specs: {[s.name for s in specs]}")
        spec = specs[0]
        name = directory.name
        records.append(
            Record(
                name=name,
                directory=directory,
                spec=spec,
                lock=locks.get(name, {}),
            )
        )
    return sorted(records, key=lambda r: r.name)


def source_locks(root: Path | None = None) -> dict[str, dict]:
    """Return the source lock keyed by recipe name."""
    root = factory_root(root)
    path = root / "config" / "upstream-sources.json"
    if not path.is_file():
        return {}
    document = json.loads(path.read_text())
    if document.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"{path}: expected schema {SCHEMA_VERSION}, got {document.get('schema')!r}")
    return {entry["name"]: entry for entry in document.get("packages", [])}


def recipe_files(record: Record) -> list[Path]:
    """Every file that constitutes the recipe, sorted.

    Used by the input digest so a patch change invalidates a cached build.
    The staged source archive is excluded: it is verified output, not recipe.
    """
    files = [
        path
        for path in sorted(record.directory.iterdir())
        if path.is_file() and not path.name.endswith(".tar.xz")
        and not path.name.endswith(".tar.gz")
        and not path.name.endswith(".tar.bz2")
        and not path.name.endswith(".tar.zst")
    ]
    return files