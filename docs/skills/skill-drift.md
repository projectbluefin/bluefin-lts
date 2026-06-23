---
name: bluefin-lts-skill-drift
version: "1.0"
last_updated: 2026-06-23
tags: [skills, ci, drift-check]
description: >-
  How the skill-drift CI check works — when it fires, what it validates, how to write a
  satisfying skill update, and how to request a waiver. Load when the skill-drift check is
  failing on a PR or when deciding whether a change requires a skill file update.
metadata:
  type: procedure
---

# Skill Drift

The `skill-drift.yml` workflow fires on every PR to `testing`. It checks that changes to
code paths are accompanied by changes to skill paths. It enforces **coupling** — that docs
stay in sync with code — but does NOT check the structural quality of skill files (that is
agent self-discipline; see `skill-improvement.md`).

## How it works

`skill-drift.yml` calls `projectbluefin/actions/.github/workflows/skill-drift-check.yml@v1`
with two path lists:

```yaml
code-paths: '[".github/workflows/**", "build_scripts/**", "system_files/**",
              "system_files_overrides/**", "Containerfile", "image-versions.yaml", "Justfile"]'
skill-paths: '["docs/skills/**", "docs/*.md", "AGENTS.md"]'
```

If a PR touches any `code-paths` file and touches **no** `skill-paths` file, the check fails.

## Code path → skill file mapping

Use this when the check fires and you need to know which skill to update:

| Changed path | Update this skill |
|---|---|
| `.github/workflows/build*.yml`, `build_scripts/**`, `image-versions.yaml` | `ci-cd.md` |
| `.github/workflows/execute-release.yml`, `promote-testing-to-main.yml` | `release.md` |
| `.github/workflows/run-testsuite.yml`, `pr-e2e.yml` | `ci-cd.md` |
| `.github/workflows/skill-drift.yml` | this file (`skill-drift.md`) |
| `.github/workflows/renovate-automerge.yml` | `ci-cd.md` |
| `Containerfile` | `build.md` |
| `Justfile` | whichever skill owns the changed recipe |
| `system_files/**`, `system_files_overrides/**` | `build.md` or `packages.md` |
| `image-versions.yaml` | `ci-cd.md` |
| `.github/CODEOWNERS` | `AGENTS.md` |

Not sure? Check `docs/skills/INDEX.md`.

## What counts as a satisfying update

A passing update must:
- Name the file, workflow, hook, command, or path that changed
- State the new rule, behavior, or expectation
- Explain what an agent should now do differently

**Passing:** "Added `system_files_overrides/**` to code-paths in skill-drift.yml; changes to override files now trigger skill-drift warnings. Update `build.md` when changing system_files_overrides."

**Failing:** rewrapping text, adding unrelated notes, or touching any markdown file without explaining the implementation change.

## Waiver process

For refactoring changes with no functional impact:

1. Add to your PR description:
   ```markdown
   ## Skill drift waiver
   Changed: `.github/workflows/build-regular.yml`
   Reason: Internal variable rename only — no behavior change, no operator impact.
   ```
2. A maintainer can override the check. Do not self-waive.

## Common failure modes

- Touching `image-versions.yaml` (Renovate bump) without updating `ci-cd.md` — most Renovate bumps are mechanical; waiver is appropriate unless behavior changed
- Touching `execute-release.yml` without updating `release.md` — these are high-impact and always warrant a skill update
- Adding a new workflow without adding it to the workflow map in `ci-cd.md`
