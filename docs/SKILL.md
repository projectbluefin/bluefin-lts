---
name: bluefin-lts-index
description: >-
  Index of skill files for projectbluefin/bluefin-lts. Routes agents to the correct skill for
  build, CI/CD, CentOS-vs-Fedora package decisions, ghost homelab testing, and release/rollback
  tasks. Load this file first, then load the relevant task skill.
metadata:
  type: reference
---

# Bluefin LTS — Skill Index

Load only the skill for the task at hand. Skill files live in `docs/skills/`.

| Task | Skill file |
|---|---|
| Local builds, validation, `just` recipes, variant map | [`skills/build.md`](skills/build.md) |
| CI/CD workflows, publish logic, tag namespaces, pitfalls | [`skills/ci-cd.md`](skills/ci-cd.md) |
| CentOS vs Fedora: packages, COPR, akmods, EPEL | [`skills/centos-vs-fedora.md`](skills/centos-vs-fedora.md) |
| GNOME Shell extensions: add, remove, build patterns | [`skills/gnome-extensions.md`](skills/gnome-extensions.md) |
| Release pipeline, rollback, registry, ISO status | [`skills/release.md`](skills/release.md) |
| OEM hardware hooks, Framework/Ampere setup, hook architecture | [`skills/hardware.md`](skills/hardware.md) |

## Self-improvement mandate

When you discover a non-obvious pattern, workaround, or convention:

1. Find the relevant skill file in `docs/skills/`.
2. Add the learning as a **canonical pattern** — not a session log. Write it as a rule or runbook entry a future agent would use directly.
3. Remove or replace stale content that contradicts the new learning.
4. Commit the skill update in the **same PR** as the change that prompted it.

**Signs of a session log (don't do this):**
- Section headers with `(added YYYY-MM-DD)` dates
- "In this session we found..." narrative phrasing
- Multiple versions of the same pattern coexisting

**Signs of a good skill entry:**
- Imperative runbook format: "When X, do Y"
- The broken pattern is removed or marked wrong, not preserved alongside the fix
- Commands are copy-pasteable and tested

For skill file format conventions, see:
[`projectbluefin/actions/.github/skills/skill-improvement/SKILL.md`](https://github.com/projectbluefin/actions/blob/main/.github/skills/skill-improvement/SKILL.md)
