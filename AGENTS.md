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
bluefin-lts (PRs→testing; testing→main; main→:stable) ←── testsuite (e2e gate)
dakota  (PRs→testing; testing→main; main→:stable)    ←── testsuite (e2e gate)
                                 │
                                 ▼
                                iso (installation media)
```

**Release model:** All three repos use a PR-as-gate promotion model.
`promote-testing-to-main.yml` (calling `reusable-promote-squash.yml@v1`) maintains an
always-open `auto/promote-testing-to-main` PR. Auto-merges once gate checks pass.
`execute-release.yml` fires on merge, re-verifies cosign, and copies `:testing` → `:stable`.

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
- **Agents MUST NOT push directly to `main`.** All changes via PR. Target `testing`.
- **Releases** are cut by merging the `auto/promote-testing-to-main` PR (testing→main). `execute-release.yml` fires on the resulting push to `main` and copies `:testing`→`:stable`.
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

- `testing` — active development. All PRs target `testing`.
- `main` — stable. Advances only via `auto/promote-testing-to-main` squash merges (Tuesday 04:00 UTC). Push to main triggers `execute-release.yml`.
- `lts` — archived. No longer part of the active pipeline.

## Hard rules

- **NEVER cancel builds** — 45–90 min, set 120+ min timeout
- **Promotion PRs squash-merge by design** — `reusable-promote-squash.yml` rebuilds the squash branch fresh on every run. Do NOT manually merge the promotion PR; it auto-merges once gate checks pass.
- **NEVER re-enable LTS ISO builds** — Anaconda is broken on CentOS Stream base
- **ALWAYS explicitly enable services from common** — systemd presets shipped from `projectbluefin/common` are NOT auto-applied in Containerfile builds. Every service must have `systemctl enable <service>` in `build_scripts/40-services.sh`. Missing this causes silent failures or unbootable images (e.g. `rechunker-group-fix.service`).

## Emergency production promotion

When production is bricking machines, skip the release gate:

1. Push fix to `testing` — builds trigger automatically.
2. Wait for all 3 builds to finish (~45–90 min). Never promote before builds finish.
3. Verify the new `:testing` image has a fresh initramfs (see `docs/skills/release.md`).
4. Skopeo-copy `:testing` → `:stable` by digest using the credentials in your local keychain.
   Do not hardcode registry credentials in code or documentation.
   Full skopeo runbook: `docs/skills/release.md` — "Emergency promotion for production-bricking bugs"
5. The PR you opened for the fix will go through normal review and merge to `testing`.

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
