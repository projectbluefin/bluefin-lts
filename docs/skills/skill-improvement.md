---
name: bluefin-lts-skill-improvement
version: "1.0"
last_updated: 2026-06-23
tags: [skills, documentation, self-improvement]
description: >-
  The skill-improvement mandate — every agent session must produce a skill file update alongside
  the work. Use when completing a task and deciding whether to write a skill update, or when
  creating or updating a skill file in docs/skills/.
metadata:
  type: procedure
---

# Skill Improvement Mandate

Every agent session produces two outputs:

1. **The work** — the PR, fix, or improvement
2. **The learning** — what a future agent should know

Output 1 without Output 2 leaves the factory no smarter. The loop only compounds if agents write back.

## Contents
- [Before You Mark Work Complete](#before-you-mark-work-complete)
- [What Counts as a Learning Worth Writing Back](#what-counts-as-a-learning-worth-writing-back)
- [Where to Write It](#where-to-write-it)
- [Which Skill File to Update](#which-skill-file-to-update)
- [Canonical Skill File Format](#canonical-skill-file-format)
- [How to Commit It](#how-to-commit-it)
- [See Also](#see-also)

## Before You Mark Work Complete

Run this checklist before opening a PR for review or marking an issue done:

- [ ] Did I discover any workaround, non-obvious pattern, or convention?
- [ ] Is there a skill file for the area I worked in?
- [ ] If yes — did I update it?
- [ ] If no — did I create one?
- [ ] Is the skill file committed in **this same PR**? (Not a follow-up. Same PR.)

If all five are checked, you're done. If any are unchecked, finish them first.

## What Counts as a Learning Worth Writing Back

**Write it:**
- A workaround for an upstream bug (include component + issue link if open)
- A non-obvious pattern required for correctness
- A convention that isn't obvious from the code
- Something you had to discover by trial and error
- A common failure mode and its fix

**Don't write it:**
- One-off task notes ("use commit message X for this PR")
- Obvious things any developer would know
- Ephemeral state ("currently broken, fix pending")
- Specific SHAs, PR numbers, or point-in-time deployment state — these become misleading after the next commit
- Session logs ("In this session we found...")

## Where to Write It

| You are working in… | Write to |
|---|---|
| `projectbluefin/bluefin-lts` | `docs/skills/` in this repo (create if absent) |
| Cross-cutting (affects multiple factory repos) | Local first, then open propagation issue in `projectbluefin/actions` |
| `ublue-os/*` repos | **NEVER** — tell the human to report it manually |

## Which Skill File to Update

| Changed path | Skill to update |
|---|---|
| `.github/workflows/build*.yml`, `build_scripts/**`, `image-versions.yaml` | `ci-cd.md` |
| `.github/workflows/execute-release.yml`, `promote-testing-to-main.yml` | `release.md` |
| `.github/workflows/run-testsuite.yml`, `pr-e2e.yml` | `ci-cd.md` |
| `.github/workflows/skill-drift.yml` | `skill-drift.md` (this file) |
| `system_files/**`, `build_scripts/**` package manifests | `build.md` or `packages.md` |
| GNOME extension add/remove | `gnome-extensions.md` |
| CentOS vs Fedora package decisions | `centos-vs-fedora.md` |
| OEM hardware hooks | `hardware.md` |
| New skill file created | `docs/SKILL.md` and `docs/skills/INDEX.md` |

Not sure? Check `docs/skills/INDEX.md`.

## Canonical Skill File Format

Every skill file must have these sections. This is enforced by agent self-audit, not CI (CI gates protect image artifacts, not docs).

```markdown
---
name: <skill-name>
description: >-
  <one-line description>. Use when <specific trigger phrases>.
metadata:
  type: skill | procedure | reference | runbook
---

# <Title>

## When to Use
<bullet list of triggering conditions — specific enough to match>

## When NOT to Use
<exclusions — redirect to the correct skill>

## Core Process
<numbered workflow — imperative, copy-pasteable>

## Red Flags
<anti-patterns that signal this skill is being violated>

## Verification
<exit criteria checklist — checkboxes>

---
## Reference
<optional: detailed technical content, commands, tables>
```

**Signs of a good skill entry:**
- Imperative runbook format: "When X, do Y"
- Broken patterns are removed, not preserved alongside the fix
- Commands are copy-pasteable and tested

**Signs of a session log (do not write this):**
- Section headers with `(added YYYY-MM-DD)` dates
- "In this session we found..." narrative
- Multiple versions of the same pattern coexisting
- Resolved item lists (`✅ PR#123 merged`)
- Running status percentages

## How to Commit It

Skill file updates are doc-only — push directly to `main`, no PR required:

```bash
# Verify all staged changes are docs-only
git diff --cached --name-only  # must show only docs/* or AGENTS.md

git add docs/skills/<updated-file>.md
git commit -m "docs(skills): <what changed and why>

Assisted-by: <Model> via <Tool>"
git push origin HEAD:main
```

If the skill update is part of a code-change PR, commit it **in the same PR**, not as a follow-up.

## See Also

- [`docs/skills/skill-drift.md`](./skill-drift.md) — how the CI coupling check works
- [`docs/factory/agentic-model.md`](../factory/agentic-model.md) — hard rules including the doc-only push exception
- [`docs/factory/IMPROVEMENTS.md`](../factory/IMPROVEMENTS.md) — running record of factory improvements
- [Canonical skill format spec](https://github.com/projectbluefin/actions/blob/main/.github/skills/skill-improvement/SKILL.md) — upstream reference
