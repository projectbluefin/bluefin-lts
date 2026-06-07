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

## Self-improvement mandate

When you discover a non-obvious pattern, workaround, or convention:

1. Find or create the relevant skill file in `docs/skills/`.
2. Write the learning under a `## Learnings` or dated `### Session changes YYYY-MM-DD` heading.
3. Commit the skill update in the **same PR** as the change that prompted it.

For skill file format conventions, see:
[`projectbluefin/actions/.github/skills/skill-improvement/SKILL.md`](https://github.com/projectbluefin/actions/blob/main/.github/skills/skill-improvement/SKILL.md)
