# Bluefin LTS — Agent & Copilot Instructions

**Bluefin LTS** is the long-term support variant of Bluefin, built on CentOS Stream with bootc.
Home repo: [projectbluefin/bluefin-lts](https://github.com/projectbluefin/bluefin-lts)

> This repo is part of an agentic operating system built by agentic workflows. Agents implement.
> Humans approve design, security-sensitive changes, and merge. See also the
> [org-wide AGENTS.md](https://github.com/projectbluefin/.github/blob/main/AGENTS.md).

## Agent fast path

```
1. docs/SKILL.md                     # find the skill for your task
2. https://github.com/projectbluefin/common/blob/main/docs/factory/agentic-model.md  # cross-repo hard rules, branch targets, PR policy (canonical — in common)
3. just check && pre-commit run --all-files  # before every commit
```

**Doc-only changes** (`docs/` and `AGENTS.md`) → push directly to `main`, no PR needed.
Verify before using this exception:
```bash
git diff --cached --name-only  # must show only docs/* or AGENTS.md
```

## Skills

See [`docs/SKILL.md`](docs/SKILL.md) for the task router and [`docs/skills/INDEX.md`](docs/skills/INDEX.md) for the full catalog.

| Task | Load |
|---|---|
| Local build, validation, packages | `docs/skills/build.md` |
| CI/CD workflows, publish logic, tag namespaces | `docs/skills/ci-cd.md` |
| Release pipeline, rollback, registry, ISO status | `docs/skills/release.md` |
| CentOS-vs-Fedora package/repo decisions | `docs/skills/centos-vs-fedora.md` |
| GNOME Shell extensions (add/remove/build) | `docs/skills/gnome-extensions.md` |
| OEM hardware hooks | `docs/skills/hardware.md` |
| Writing or updating a skill file | `docs/skills/skill-improvement.md` |
| skill-drift CI check failing | `docs/skills/skill-drift.md` |
| Cross-repo rules, branch targets | [`projectbluefin/common` docs/factory/agentic-model.md](https://github.com/projectbluefin/common/blob/main/docs/factory/agentic-model.md) |


## The Self-Improvement Loop

Every session produces two outputs: the work and the learning. See [`docs/skills/skill-improvement.md`](docs/skills/skill-improvement.md) for the full mandate, canonical skill format, and commit procedure.

---

## Human Decision Points — Stop and Ask

Agents implement autonomously **except** at these gates:

| Gate | When |
|---|---|
| **Design Gate** | Architecture changes, new subsystem design, behavioral changes visible to users |
| **Security Gate** | Auth, signing, supply chain, secrets handling, COPR/third-party sources |
| **Breakage Gate** | Cross-repo breaking changes — removing/renaming inputs, changing defaults that affect consuming repos |
| **Merge Gate** | Final PR approval and merge — always human |

When in doubt, open a draft PR with your implementation and ask explicitly.

---

## Verification — Implement and Verify; Humans Approve and Merge

Do not request review without evidence. Before opening a PR for review:
- Link to a CI run, workflow run, or test output that exercises your change
- If no automated test exists, describe how you manually verified the change
- Skill file update must be committed in the **same PR** (not a follow-up)

---

## 🚫 Absolute Prohibition — ublue-os org

**NEVER create issues, pull requests, comments, forks, webhook calls, API writes, automated
reports, or any other programmatic action targeting any `ublue-os/*` repository.**

If a task requires touching upstream `ublue-os` repos → **stop and tell the human to report it manually.**

---

## Org pipeline — projectbluefin

### Repo map

```
common ──────────────────────────┐
(shared OCI layer)               │
                                 ▼
bluefin  (PRs→testing; testing→main; main→:stable)   ←── testsuite (e2e gate)
bluefin-lts (PRs→testing*; testing→main; main→:lts)  ←── testsuite (e2e gate)
dakota  (PRs→testing; testing→main; main→:stable)    ←── testsuite (e2e gate)
                                 │
                                 ▼
                                iso (installation media)
```

(*) bluefin-lts currently targets `main` for PRs; migration to `testing` is the factory standard
and is tracked in the branch model section below.

**Release model:** All three repos use a PR-as-gate promotion model.
`promote-testing-to-main.yml` (calling `reusable-promote-squash.yml@v1`) maintains an
always-open `auto/promote-testing-to-main` PR. Merging it (requires 2 `projectbluefin/maintainers`
approvals plus passing gate checks) cuts a release. `execute-release.yml` fires on merge,
re-verifies cosign, and copies `:testing` → target tag.

### Issue lifecycle

`filed → approved → queued → claimed → done`

| Stage | How |
|---|---|
| `filed` | Issue opened |
| `approved` | Maintainer adds `status/approved` or comments `/approve` |
| `queued` | `status/queued` auto-added alongside approval |
| `claimed` | Comment `/claim` — assigned, removed from pool |
| `done` | Fix shipped + 3× `ujust verify` or maintainer override |

No PR activity in 7 days returns a claimed issue to the queue automatically.

**When an agent opens a PR:** remove `status/queued` from the issue, add `status/claimed` to both the issue and the PR. This signals the work is done and a human is next to review.

### PR comment policy

One comment per PR event, max. Combine all findings. Never post a follow-up — edit the existing comment.
Never duplicate GitHub UI state (approvals, CI status).
Test reports: what ran + pass/fail + blockers only. No diff summaries.
@ mentions only when asking someone to do something specific. Never standalone.
When in doubt, post nothing.

### Mandatory gates

- `just check && pre-commit run --all-files` before every commit
- **Pre-commit guard:** `no-floating-action-tags` blocks third-party `@main`/`@v*` floating action tags at commit time. `projectbluefin/actions/`, `projectbluefin/bonedigger/`, and `projectbluefin/testsuite/` refs are intentional managed tags and are exempted. `no-sha-pins-for-internal-actions` blocks SHA pins on `projectbluefin/actions` and `projectbluefin/testsuite` — both use `@v1` managed tags.
- PR title: Conventional Commits format
- Attribution on every AI-authored commit: `Assisted-by: <Model> via <Tool>`
- Max 4 open PRs at a time per agent
- No WIP PRs
- **Agents MUST NOT push directly to `main`.** All changes via PR. Branch protection enforces this (requires 2 `projectbluefin/maintainers` approvals).
- **Agents MUST NOT push directly to `lts`.** Land in `main` first; `execute-release.yml` handles copying `:testing`→`:lts` on promotion PR auto-merge.
- **Releases** are cut by merging the `auto/promote-testing-to-main` PR. No `scheduled-lts-release.yml` workflow exists — do not reference it.
- **bluefin-lts workflow path overrides are intentional:** use `build_scripts/` and `image-versions.yaml`, not bluefin's `build_files/` and `image-versions.yml`.
- **`.github/workflows/`, `Justfile`, and `build_scripts/` are CODEOWNERS-protected** — PRs touching these paths require maintainer review.

## Skills

See [`docs/SKILL.md`](docs/SKILL.md) for the full index. Load only what the task needs:

| Task | Load |
|---|---|
| Local build, validation, packages | `docs/skills/build.md` |
| CI/CD workflows, publish logic, tag namespaces | `docs/skills/ci-cd.md` |
| CentOS-vs-Fedora package/repo decisions | `docs/skills/centos-vs-fedora.md` |
| GNOME Shell extensions (add/remove/build) | `docs/skills/gnome-extensions.md` |
| Release, rollback, registry, ISO status | `docs/skills/release.md` |

## Branch model

### Current state

- `main` — active development. All PRs currently target `main`.
- `lts` — production releases only. Promotion is one-way: `main → lts`.

### Target state (factory alignment — in progress)

bluefin and dakota use `testing` as the PR target with `testing→main` promotion. bluefin-lts
currently diverges by targeting `main` directly. The factory standard requires all three repos
to align on the same model. **Migration tasks (tracked in projectbluefin/bluefin-lts):**

1. Create `testing` branch in bluefin-lts (from current `main`)
2. Change branch protection: `testing` becomes the PR target; `main` receives promotion commits only
3. Update `promote-testing-to-main.yml` to use the `reusable-promote-squash.yml` defaults (source=testing, target=main)
4. Update `post-merge-e2e.yml` to trigger on `testing` branch builds
5. Keep a separate `main→lts` promotion step for the stable release
6. Update `sync-main-to-testing.yml` to function as a pure post-promotion sync

Until migration is complete, use `main` as the PR target for bluefin-lts. Do not target `lts` directly.

## Hard rules

- **NEVER cancel builds** — 45–90 min, set 120+ min timeout
- **Promotion PRs squash-merge by design** — `reusable-promote-squash.yml` rebuilds the squash branch fresh from the target branch on every run. Do NOT manually merge the promotion PR; the PR auto-merges once all gate checks pass (`lts` requires 0 approvals — gate checks are the only gate).
- **NEVER re-enable LTS ISO builds** — Anaconda is broken on CentOS Stream base
- **NEVER commit directly to `lts` branch** — land in `main` first
- **NEVER merge `lts→main`** — flow is one-way: `main→lts` only
- **ALWAYS explicitly enable services from common** — systemd presets shipped from `projectbluefin/common` are NOT auto-applied in Containerfile builds. Every service must have `systemctl enable <service>` in `build_scripts/40-services.sh`. Missing this causes silent failures or unbootable images (e.g. `rechunker-group-fix.service`).

## Emergency production promotion

When production is bricking machines, skip the release gate:

1. Push fix to `main` — builds trigger automatically on `main` and `testing`.
2. Wait for all 3 builds to finish (~45–90 min). Never promote before builds finish.
3. Verify the new `:testing` image has a fresh initramfs (see `docs/skills/release.md`).
4. Skopeo-copy `:testing` → `:lts` by digest using the credentials in your local keychain.
   Do not hardcode registry credentials in code or documentation.
   Full skopeo runbook: `docs/skills/release.md` — "Emergency promotion for production-bricking bugs"
5. The PR you opened for the fix will go through normal review and merge to `main`.

## Commit standards

### Format (required)

[Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <description>`

Common types: `feat` `fix` `docs` `ci` `refactor` `chore` `build`

### AI attribution (required on every AI-authored commit)

```
feat(ci): add container build optimization

Optimize multi-stage build to reduce image size.

Assisted-by: Claude Sonnet 4.5 via pi
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

### SHA pinning (third-party actions)

All `uses:` references to **external** actions must be pinned to a full commit SHA with a version
comment. Never use floating `@main` or `@vN` tags for third-party actions.
`projectbluefin/actions` refs (`@v1`) are intentional managed tags and are exempt.
`projectbluefin/testsuite` refs use `@v1` in `run-testsuite.yml`; the testsuite's
`update-v1-tag.yml` auto-tracks `v1` to main on every merge — no manual SHA bumps needed.

---

## Quick commands

```bash
just check && pre-commit run --all-files   # validate before every commit
just build bluefin lts                     # full build (120+ min timeout)
```
