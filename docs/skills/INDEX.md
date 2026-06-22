---
name: bluefin-lts-skill-index
description: >-
  Full catalog of skill files for projectbluefin/bluefin-lts. Routes agents to the correct
  skill for any task. Load this first, then load the task skill.
metadata:
  type: reference
---

# docs/skills — Index

All skill files live in `docs/skills/`. Load only the skill for the task at hand.

## What belongs here

Operational knowledge: runbooks, workflows, patterns, pitfalls.
Written as timeless rules, not session logs.

## What does NOT belong here

- Session notes or dated entries
- Resolved item lists
- GitHub issue or PR numbers as inline state
- Status percentages or coverage numbers

## Factory docs

| File | What it covers |
|---|---|
| [`../factory/README.md`](../factory/README.md) | Factory structure, data flow, open gaps, parity matrix |
| [`projectbluefin/common docs/factory/README.md`](https://github.com/projectbluefin/common/blob/main/docs/factory/README.md) | Factory structure, data flow, open gaps, and current improvement guidance |
| [`../factory/agentic-model.md`](../factory/agentic-model.md) | Cross-repo hard rules, branch targets, PR comment policy, ublue-os prohibition |

## Skill docs

| File | What it covers |
|---|---|
| [`build.md`](build.md) | Local builds, `just` recipes, variant map, validation commands |
| [`ci-cd.md`](ci-cd.md) | Workflow map, publish logic, tag namespaces, promotion flow, pitfalls — use when debugging build triggers or fixing the release pipeline |
| [`release.md`](release.md) | Production release procedure, emergency rollback, registry verification, ISO status |
| [`centos-vs-fedora.md`](centos-vs-fedora.md) | Package decisions: CentOS vs Fedora, COPR, akmods, EPEL |
| [`gnome-extensions.md`](gnome-extensions.md) | GNOME Shell extensions: add, remove, build patterns |
| [`hardware.md`](hardware.md) | OEM hardware hooks, Framework/Ampere setup, hook architecture |
| [`packages.md`](packages.md) | Package manifests, cadence intervals, package addition/removal patterns |
| [`skill-improvement.md`](skill-improvement.md) | **The skill-improvement mandate** — how to write skill files, canonical format, commit procedure |
| [`skill-drift.md`](skill-drift.md) | How the skill-drift CI coupling check works, path mapping, waiver process |
| [`testing.md`](testing.md) | When to use ghost lab (KubeVirt VM) vs podman headless for testing changes |

## Task → Skill

| I need to… | Load |
|---|---|
| Build locally or validate before pushing | `build.md` |
| Debug why a build didn't trigger or why images weren't published | `ci-cd.md` |
| Understand the workflow map or event truth table | `ci-cd.md` |
| Cut a release or check release status | `release.md` |
| Emergency rollback of a production image | `release.md` |
| Verify published images or digests | `release.md` |
| Add or remove a package | `packages.md` |
| Add or remove a GNOME extension | `gnome-extensions.md` |
| Make a CentOS vs Fedora package decision | `centos-vs-fedora.md` |
| Work on OEM hardware hooks | `hardware.md` |
| Write or update a skill file | `skill-improvement.md` |
| Understand why the skill-drift CI check fired | `skill-drift.md` |
| Test a change in the ghost lab or podman headless | `testing.md` |
| Understand cross-repo rules or branch targets | `../factory/agentic-model.md` |
| Understand what improvement is next for the factory | `https://github.com/projectbluefin/common/blob/main/docs/factory/README.md` |
