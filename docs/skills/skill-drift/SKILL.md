---
name: skill-drift
description: >-
  Diagnose and resolve documentation-to-code drift checks. Use when the skill-drift workflow
  reports a mismatch or a source path has no owning skill.
---

# Skill drift

## When to use

Use when the skill-drift workflow reports that an implementation change lacks a
documentation change, or when a source path has no documented owner.

## When not to use

Do not use for unrelated Markdown wording or formatting changes.

## How the check works

The workflow delegates to the repository's managed skill-drift check. It compares
these implementation paths with documentation paths:

```yaml
code-paths:
  - .github/workflows/**
  - build_scripts/**
  - system_files/**
  - system_files_overrides/**
  - Containerfile
  - image-versions.yaml
  - Justfile
skill-paths:
  - docs/skills/**
  - docs/*.md
  - AGENTS.md
```

If a pull request targeting the branch configured in
`.github/workflows/skill-drift.yml` changes an implementation path without a
skill-path change, the check fails.

## Procedure

1. Read `.github/workflows/skill-drift.yml` and the changed source path.
2. Find the narrowest existing skill that owns the behavior.
3. Update that skill with the new rule, path, command, or expected evidence.
4. Update the skill index only when a skill is added, renamed, or retired.
5. If the change is documentation-neutral, explain the reason in the pull request
   using the repository's waiver process.
6. Verify links, index entries, and skill metadata locally.

## Source-path ownership

| Changed path | Owning skill |
|---|---|
| `.github/workflows/build*.yml`, `build_scripts/**`, `image-versions.yaml` | [`build`](../build/SKILL.md) or [`ci-cd`](../ci-cd/SKILL.md) |
| Promotion or stable publication workflows | [`release`](../release/SKILL.md) |
| Test-suite and end-to-end workflows | [`testing`](../testing/SKILL.md) or [`ci-cd`](../ci-cd/SKILL.md) |
| `.github/workflows/skill-drift.yml` | This skill |
| `Containerfile` | [`build`](../build/SKILL.md) |
| `Justfile` | The skill owning the changed recipe |
| `system_files/**`, `system_files_overrides/**` | [`build`](../build/SKILL.md), [`packages`](../packages/SKILL.md), or [`hardware`](../hardware/SKILL.md) |
| `.github/CODEOWNERS` | [`AGENTS.md`](../../../AGENTS.md) |

When ownership is unclear, inspect the source and index before creating a new
skill.

## Satisfying update

A useful update names the changed file, workflow, command, or path; states the
new rule or behavior; and explains what an agent should do differently.

Rewrapping text or touching an unrelated Markdown file is not a satisfying
update.

## Common rationalizations

- “The old skill path is harmless.” Update the index and links together.
- “A Markdown change is enough.” State the implementation behavior the agent must
  now handle differently.
- “The workflow comment is authoritative.” Read the executable workflow first.

## Red flags

- A code path has no owning skill.
- A skill documents a deleted source path.
- The skill claims a branch, trigger, permission, or schedule that differs from
  the workflow.
- A waiver hides a behavior change.

## Verification

```bash
python3 scripts/check-skill-docs.py
actionlint .github/workflows/*.yml
pre-commit run --all-files
```
