#!/usr/bin/env python3
"""Validate the repository's lazy-loaded skill documentation."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "docs" / "skills"
INDEX = SKILLS / "INDEX.md"
MAX_LINES = 500


def front_matter(path: Path) -> tuple[dict[str, str], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return {}, ["missing YAML front matter"]
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, ["unterminated YAML front matter"]

    values: dict[str, str] = {}
    errors: list[str] = []
    for line in lines[1:end]:
        match = re.match(r"^(name|description):\s*(.*)$", line)
        if match:
            value = match.group(2).strip(" >-")
            values[match.group(1)] = value or "present"
    for key in ("name", "description"):
        if key not in values:
            errors.append(f"missing front matter field: {key}")
    return values, errors


def markdown_targets(path: Path) -> list[tuple[str, int]]:
    targets: list[tuple[str, int]] = []
    pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for target in pattern.findall(line):
            if not target.startswith(("http://", "https://", "mailto:", "#")):
                targets.append((target.split("#", 1)[0], number))
    return targets


def main() -> int:
    errors: list[str] = []
    skill_files = sorted(SKILLS.glob("*/SKILL.md"))
    if not skill_files:
        errors.append("no skill entry files found")

    indexed = set(re.findall(r"\]\(([^)]+/SKILL\.md)\)", INDEX.read_text(encoding="utf-8")))
    expected = {path.relative_to(SKILLS).as_posix() for path in skill_files}
    missing = expected - indexed
    stale = indexed - expected
    if missing:
        errors.append("unindexed skills: " + ", ".join(sorted(missing)))
    if stale:
        errors.append("missing skill files: " + ", ".join(sorted(stale)))

    for path in skill_files:
        values, metadata_errors = front_matter(path)
        for error in metadata_errors:
            errors.append(f"{path.relative_to(ROOT)}: {error}")
        expected_name = path.parent.name
        if values.get("name") and values["name"] != expected_name:
            errors.append(
                f"{path.relative_to(ROOT)}: name {values['name']!r} "
                f"does not match directory {expected_name!r}"
            )
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_LINES:
            errors.append(f"{path.relative_to(ROOT)}: {line_count} lines exceeds {MAX_LINES}")

    documentation_files = [
        ROOT / name for name in ("AGENTS.md", "README.md", "CONTRIBUTING.md", "SECURITY.md")
    ]
    documentation_files += list((ROOT / "docs").glob("*.md"))
    documentation_files += [INDEX, *skill_files, *SKILLS.glob("*/references/*.md")]
    for path in documentation_files:
        for target, line in markdown_targets(path):
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                errors.append(f"{path.relative_to(ROOT)}:{line}: missing link target {target}")

    legacy = sorted(SKILLS.glob("*.md"))
    legacy = [path for path in legacy if path.name != "INDEX.md"]
    for path in legacy:
        errors.append(f"legacy flat skill file remains: {path.relative_to(ROOT)}")

    if errors:
        print("Skill documentation check failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Skill documentation OK: {len(skill_files)} skills, max entry size {MAX_LINES} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
