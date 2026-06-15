# Bluefin LTS — Agent & Copilot Instructions

**Bluefin LTS** is the long-term support variant of Bluefin, built on CentOS Stream with bootc.
Home repo: [projectbluefin/bluefin-lts](https://github.com/projectbluefin/bluefin-lts)

> This repo is part of an agentic operating system built by agentic workflows. Agents implement.
> Humans approve design, security-sensitive changes, and merge. See also the
> [org-wide AGENTS.md](https://github.com/projectbluefin/.github/blob/main/AGENTS.md).

## The Self-Improvement Loop

Every agent session produces two outputs:
1. **The work** — the PR, fix, or improvement.
2. **The learning** — what you discovered that a future agent should know.

Output 1 without Output 2 leaves the system no smarter. **The loop only compounds if agents write back.**

```
Agent works on task
  └─ discovers pattern / workaround / convention
       └─ writes it to the relevant skill file in docs/skills/
            └─ commits in the same PR
                 └─ next agent starts smarter
                      └─ loop
```

**Before marking your work complete, verify:**
- [ ] Did I discover a workaround, non-obvious pattern, or convention?
- [ ] Is there a skill file for the area I worked in (`docs/skills/`)?
- [ ] If yes — did I update it?
- [ ] If no — did I create one and add it to `docs/SKILL.md`?
- [ ] Is the skill file committed in the **same PR** as the change?

### What counts as a learning worth writing back

**Write it:**
- A workaround for an upstream bug (include component + issue link if open)
- A non-obvious pattern required for correctness
- A convention that isn't obvious from the code
- Something you had to discover by trial and error

**Don't write it:**
- One-off task notes ("use commit message X for this PR")
- Obvious things any developer would know
- Ephemeral state ("currently broken, fix pending")
- Specific SHAs, PR numbers, or point-in-time deployment state — these become misleading after the next commit

### Where learnings live

| You are working in... | Write to |
|---|---|
| `projectbluefin/bluefin-lts` | `docs/skills/` in this repo (create if absent) |
| `projectbluefin/actions` | `docs/skills/` AND `.github/skills/` in that repo |
| Cross-cutting (affects multiple repos) | Local first, then open propagation issue in `projectbluefin/actions` |
| `ublue-os/*` repos | **NEVER** — see the prohibition below |

See [`docs/SKILL.md`](docs/SKILL.md) for the skill index.
For skill file format, see
[`projectbluefin/actions/.github/skills/skill-improvement/SKILL.md`](https://github.com/projectbluefin/actions/blob/main/.github/skills/skill-improvement/SKILL.md).

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
bluefin  (main→stable)       ←── images ──→ testsuite (e2e gate)
bluefin-lts (main→lts)       ←── images ──→ testsuite (e2e gate)
dakota  (main→stable)        ←── images ──→ testsuite (e2e gate)
                                 │
                                 ▼
                                iso (installation media)
```

**Release model (as of 2026-06-09):** All three repos use a PR-as-gate promotion model.
`promote-testing-to-main.yml` maintains an always-open `auto/promote-testing-to-main` PR.
Merging it (requires 2 `projectbluefin/maintainers` approvals) cuts a release.
`execute-release.yml` fires on merge, re-verifies cosign, copies `:testing` → target tag.

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

- `just check && just lint` before every commit
- **Pre-commit guard:** `no-floating-action-tags` blocks third-party `@main`/`@v*` floating action tags at commit time. `projectbluefin/` refs (`@v1`, `@main`) are intentional managed tags and are exempted.
- PR title: Conventional Commits format
- Attribution on every AI-authored commit: `Assisted-by: <Model> via <Tool>`
- Max 4 open PRs at a time per agent
- No WIP PRs
- **Agents MUST NOT push directly to `main`.** All changes via PR. Branch protection enforces this (requires 2 `projectbluefin/maintainers` approvals).
- **Agents MUST NOT push directly to `lts`.** Land in `main` first; `execute-release.yml` fast-forwards `lts` on promotion PR merge.
- **Releases** are cut by merging the `auto/promote-testing-to-main` PR. `scheduled-lts-release.yml` has been deleted — do not reference it.
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

- `main` — active development (default). All PRs target `main`.
- `lts` — production releases only. Promotion is one-way: `main → lts`.

## Hard rules

- **NEVER cancel builds** — 45–90 min, set 120+ min timeout
- **Promotion PRs (`main→lts`) squash-merge by design** — `reusable-promote-squash.yml` rebuilds the squash branch fresh from `lts` on every run. Do NOT manually merge the promotion PR; `allow_auto_merge` is enabled and the PR merges itself once 2 approvals land and all gate checks pass.
- **NEVER re-enable LTS ISO builds** — Anaconda is broken on CentOS Stream base
- **NEVER commit directly to `lts` branch** — land in `main` first
- **NEVER merge `lts→main`** — flow is one-way: `main→lts` only
- **ALWAYS explicitly enable services from common** — systemd presets shipped from `projectbluefin/common` are NOT auto-applied in Containerfile builds. Every service must have `systemctl enable <service>` in `build_scripts/40-services.sh`. Missing this causes silent failures or unbootable images (e.g. `rechunker-group-fix.service`).

## Emergency production promotion

When production is bricking machines, skip the release gate:

1. Push fix to `main` — builds trigger automatically on `main` and `testing`.
2. Wait for all 3 builds to finish (~45–90 min). Never promote before builds finish.
3. Verify the new `:testing` image has a fresh initramfs (see `docs/skills/release.md`).
4. Skopeo-copy `:testing` → `:lts` by digest:
   ```bash
   GHCR_TOKEN=$(gh auth token)
   for IMAGE in bluefin-lts bluefin-lts-hwe bluefin-lts-nvidia; do
     DIGEST=$(skopeo inspect --creds "castrojo:${GHCR_TOKEN}" docker://ghcr.io/projectbluefin/${IMAGE}:testing | python3 -c "import json,sys; print(json.load(sys.stdin)['Digest'])")
     skopeo copy \
       --src-creds "castrojo:${GHCR_TOKEN}" \
       --dest-creds "castrojo:${GHCR_TOKEN}" \
       docker://ghcr.io/projectbluefin/${IMAGE}@${DIGEST} \
       docker://ghcr.io/projectbluefin/${IMAGE}:lts
   done
   ```
5. The PR you opened for the fix will go through normal review and auto-merge to `main`.

Full runbook: `docs/skills/release.md` — "Emergency promotion for production-bricking bugs"

## Commit standards

### Format (required)

[Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <description>`

Common types: `feat` `fix` `docs` `ci` `refactor` `chore` `build`

### AI attribution (required on every AI-authored commit)

```
feat(ci): add container build optimization

Optimize multi-stage build to reduce image size.

Assisted-by: Claude Sonnet 4.6 via GitHub Copilot
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

### SHA pinning (third-party actions)

All `uses:` references to **external** actions must be pinned to a full commit SHA with a version
comment. Never use floating `@main` or `@vN` tags for third-party actions.
`projectbluefin/` refs (`@v1`, `@main`) are intentional managed tags and are exempt.

---

## Quick commands

```bash
just check && just lint     # validate before every commit
just build bluefin lts      # full build (120+ min timeout)
```
