---
name: bluefin-lts-index
description: >-
  Index of skill files for projectbluefin/bluefin-lts. Routes agents to the correct skill for
  any task. Load this file first, then load the relevant task skill.
metadata:
  type: reference
---

# Bluefin LTS — Skill Router

For the full skill catalog, see [`docs/skills/INDEX.md`](skills/INDEX.md).

For the canonical skill format and improvement mandate, see [`docs/skills/skill-improvement.md`](skills/skill-improvement.md).

For cross-repo hard rules and branch targets, see [`docs/factory/agentic-model.md`](factory/agentic-model.md).

## Agent fast path

```
1. docs/skills/INDEX.md          # find the skill for your task
2. docs/factory/agentic-model.md # cross-repo rules if working across repos
3. just check && pre-commit run --all-files  # before every commit
```

## Quick task routing

| Task | Load |
|---|---|
| Local builds, validation, `just` recipes | [`skills/build.md`](skills/build.md) |
| CI/CD workflows, publish logic, tag namespaces, pitfalls | [`skills/ci-cd.md`](skills/ci-cd.md) |
| Release pipeline, rollback, registry, ISO status | [`skills/release.md`](skills/release.md) |
| CentOS vs Fedora: packages, COPR, akmods, EPEL | [`skills/centos-vs-fedora.md`](skills/centos-vs-fedora.md) |
| GNOME Shell extensions: add, remove, build patterns | [`skills/gnome-extensions.md`](skills/gnome-extensions.md) |
| OEM hardware hooks, Framework/Ampere setup | [`skills/hardware.md`](skills/hardware.md) |
| Package manifests, cadence, add/remove patterns | [`skills/packages.md`](skills/packages.md) |
| Testing: podman headless vs KubeVirt VM, ghost lab | [`skills/testing.md`](skills/testing.md) |
| Writing or updating a skill file | [`skills/skill-improvement.md`](skills/skill-improvement.md) |
| skill-drift CI check failing | [`skills/skill-drift.md`](skills/skill-drift.md) |
| Cross-repo rules, branch targets | [`factory/agentic-model.md`](factory/agentic-model.md) |

## Self-improvement mandate

When you discover a non-obvious pattern, workaround, or convention:

1. Find the relevant skill file in `docs/skills/`.
2. Add the learning as a **timeless rule** — not a session log.
3. Remove or replace stale content that contradicts the new learning.
4. Commit the skill update in the **same PR** as the change (or push directly to `main` for doc-only changes).

See [`docs/skills/skill-improvement.md`](skills/skill-improvement.md) for the full mandate and canonical format.
