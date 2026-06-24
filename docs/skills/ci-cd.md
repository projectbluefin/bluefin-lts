---
name: bluefin-lts-ci-cd
description: >-
  CI/CD workflow map, publish logic, tag namespaces, promotion flow, and pitfalls for
  projectbluefin/bluefin-lts. Use when debugging build triggers, understanding why images were
  not published, fixing the release pipeline, authoring new workflows, or investigating
  cosign/E2E gate failures.
metadata:
  type: skill
---

# CI/CD

## When to Use

- Debugging why a build didn't trigger or images weren't published
- Understanding the workflow map (which file does what)
- Fixing or authoring a GitHub Actions workflow
- Investigating cosign verification failures
- Understanding the promotion flow (`testing → main → :stable`)
- Diagnosing E2E gate failures or Renovate auto-merge issues
- Checking tag/stream_name routing for a given branch

## When NOT to Use

- Cutting a release or verifying published images → `release.md`
- Adding/removing packages or changing the Containerfile → `build.md`
- Making CentOS vs Fedora package decisions → `centos-vs-fedora.md`

## Core Process

### Debug: why didn't my build trigger?

1. Check the event truth table (Reference below) for the branch + event combination.
2. Verify `detect-changes` didn't skip the build (only fires when image-relevant paths change).
3. Check for zombie runs holding the concurrency group:
   ```bash
   gh run list --repo projectbluefin/bluefin-lts --status in_progress \
     --json databaseId,name,createdAt --jq '.[] | [.name, .createdAt, .databaseId] | @tsv'
   # Cancel zombies:
   gh run cancel <id> --repo projectbluefin/bluefin-lts
   ```

### Debug: why isn't `:testing` updated?

Builds publish `:testing` directly on push to the `testing` branch. If `:testing` is stale, check the build run:

```bash
gh run list --repo projectbluefin/bluefin-lts \
  --workflow "Build Bluefin LTS" --limit 5 \
  --json conclusion,headBranch,createdAt,url \
  --jq '.[] | [.conclusion, .headBranch, .createdAt, .url] | @tsv'
```

### Debug: cosign verification failure

See Reference — Cosign verification section below. The cert identity regexp must match
`^https://github\.com/projectbluefin/(bluefin-lts|actions)/\.github/workflows/`.

### Add a new workflow

1. Create the caller in `.github/workflows/` using one of the existing callers as a template.
2. All third-party `uses:` must be SHA-pinned with a version comment.
3. `projectbluefin/actions` refs use `@v1` (managed tags, not SHA-pinned).
4. Update the workflow map in this file (`ci-cd.md`) Reference section.
5. Run `actionlint .github/workflows/<new-file>.yml` before committing.

## Red Flags

- **Floating third-party action tags** (`@main`, `@v2`) — `no-floating-action-tags` pre-commit hook blocks these. `projectbluefin/actions@v1` is exempt.
- **SHA-pinning `projectbluefin/testsuite`** — use `@v1`; testsuite auto-tracks it. The `no-sha-pins-for-internal-actions` hook blocks SHA pins on both `actions` and `testsuite`.
- **Adding `workflows: write` to a job** — not a valid `GITHUB_TOKEN` scope; causes silent failures.
- **Triggering on `push: main`** — builds fire on push to `testing`, not `main`. `main` only triggers `execute-release.yml`.
- **Calling the testsuite `e2e.yml` directly** — always call via `run-testsuite.yml`; never call the testsuite directly.
- **`stream_name: lts` in a build caller** — there is no `lts` stream; build callers use `stream_name: testing`. `execute-release.yml` uses skopeo copy, not reusable-build.
- **`startup_failure` with no log** — means a permission scope required by a nested reusable workflow is not granted by the caller job. See Reference — startup_failure diagnosis.
- **`use_merge_queue: false` on main** — main has a merge queue ruleset (17070416); always use `use_merge_queue: true` so `enqueuePullRequest` fires and the PR squash-merges.

## Verification

After any workflow change:

- [ ] `actionlint .github/workflows/<changed>.yml` passes
- [ ] `just check && pre-commit run --all-files` passes
- [ ] No floating third-party action tags (pre-commit guard catches this)
- [ ] `run-testsuite.yml` uses `@v1`, not a SHA pin — Renovate is disabled for this ref
- [ ] New workflow added to the workflow map in this file
- [ ] If workflow touches the release pipeline → `release.md` updated too

---

## Reference

## Contents
- [Workflow map](#workflow-map)
- [Branches and tags](#branches-and-tags)
- [Promotion flow](#promotion-flow-testingmain)
- [stream_name routing](#stream_name--how-tags-are-determined)
- [Event truth table](#event-truth-table)
- [Centralized CI — projectbluefin/actions](#centralized-ci--projectbluefinaactions)
- [Schedule ownership](#schedule-ownership)
- [Renovate auto-merge pipeline](#renovate-auto-merge-pipeline)
- [Daily release pipeline](#daily-release-pipeline)
- [Release pipeline pitfalls](#release-pipeline-pitfalls)
- [GHCR Package Access](#ghcr-package-access--always-use-githubtoken-never-custom-pats)
- [SBOM rules](#sbom-rules)
- [Condition quick reference](#condition-quick-reference)

## Workflow map

| File | Role |
|---|---|
| `build-regular.yml` | caller for `bluefin-lts` — fires on push to `testing` |
| `build-regular-hwe.yml` | caller for `bluefin-lts-hwe` (HWE kernel) — fires on push to `testing` |
| `build-nvidia.yml` | caller for `bluefin-lts-hwe-nvidia` (NVIDIA/AI) — fires on push to `testing` |
| `promote-testing-to-main.yml` | maintains always-open `auto/promote-testing-to-main` PR (`testing → main`); calls `reusable-promote-squash.yml@v1` with `source_branch=testing, target_branch=main`, daily 04:00 UTC cron |
| `execute-release.yml` | fires on push to `main` when commit message matches `"^chore: promote testing to main"`; cosign re-verify, skopeo `:testing` → `:stable`, GitHub release |
| ~~`sync-main-to-lts.yml`~~ | **deleted** — replaced by PR-as-gate promotion model |
| ~~`scheduled-lts-release.yml`~~ | **deleted** — releases cut by merging the promotion PR |
| ~~`generate-release.yml`~~ | **deleted** — release creation handled by `execute-release.yml` |
| ~~`lifecycle-caller.yml`~~ | **deleted** |
| ~~`post-merge-e2e.yml`~~ | **deleted** — builds publish `:testing` directly; no E2E gate |
| ~~`sync-main-to-testing.yml`~~ | **deleted** — inverted flow no longer needed |
| `pr-testsuite.yml` | runs **`validate-pr@v1`** (just check, shellcheck, hadolint, pre-commit) + **e2e smoke** on every PR; only `Lint & syntax` is a required check |
| `pr-e2e.yml` | advisory PR E2E gate; composes `system_files/` changes on top of `bluefin-lts:testing` and runs smoke suite; non-blocking; only fires when image-relevant paths change |
| `pr-e2e-smoke.yml` | informational E2E smoke on every PR; always fails due to `ublue-os/` prefix mismatch in testsuite (issue #34, testsuite#412); never block merge on this |
| `run-testsuite.yml` | canonical wrapper for calling `projectbluefin/testsuite` — always call via this file, never call the testsuite `e2e.yml` directly; uses `@v1` managed tag, auto-tracked to main by testsuite's `update-v1-tag.yml` (see below) |
| `renovate-automerge.yml` | auto-merges Renovate/mergeraptor PRs when pr-testsuite passes |
| `pr-e2e.yml` | advisory PR E2E gate; composes `system_files/` changes on top of `bluefin-lts:testing` and runs smoke suite; non-blocking; only fires when image-relevant paths change |
| `lifecycle-caller.yml` | issue and PR lifecycle automation (bonedigger pipeline via `projectbluefin/common`) |
| `skill-drift.yml` | warns on PRs that change CI/build/system files without updating docs/skills |
| `validate-renovate.yaml` | validates `.github/renovate.json5` on relevant PRs and pushes |
| ~~`build-gdx.yml`~~ | **renamed** to `build-nvidia.yml` (PR #225, 2026-06-14) |
| ~~`build-dx.yml`~~ | **deleted** — no DX variant in LTS |
| ~~`build-dx-hwe.yml`~~ | **deleted** — no DX HWE variant |
| ~~`build-gnome50.yml`~~ | **deleted 2026-05-30** — GNOME 50 is now the default |
| ~~`reusable-build-image.yml`~~ | **deleted** — replaced by `projectbluefin/actions/.github/workflows/reusable-build.yml@v1` |
| ~~`create-lts-pr.yml`~~ | **deleted 2026-05-30** — replaced by `sync-main-to-lts.yml` |

## Branches and tags

| Branch | Image | Tags | When |
|---|---|---|---|
| `testing` | `bluefin-lts` | `testing`, `testing-YYYYMMDD` | every push/merge to `testing` |
| `testing` | `bluefin-lts-hwe` | `testing`, `testing-YYYYMMDD` | every push/merge to `testing` |
| `testing` | `bluefin-lts-hwe-nvidia` | `testing`, `testing-YYYYMMDD` | every push/merge to `testing` |
| `main` (via execute-release) | `bluefin-lts` | `stable`, `stable-YYYYMMDD` | on promotion PR merge (execute-release.yml) |
| `main` (via execute-release) | `bluefin-lts-hwe` | `stable`, `stable-YYYYMMDD` | on promotion PR merge (execute-release.yml) |
| `main` (via execute-release) | `bluefin-lts-hwe-nvidia` | `stable`, `stable-YYYYMMDD` | on promotion PR merge (execute-release.yml) |

`push` to `main` does NOT trigger any build workflow. Builds fire on `testing` only.

## Branch model

- `testing` — all PRs target this branch. Builds push `:testing` on every push.
- `main` — production source. Advances only via squash promotion from `testing`. Triggers `execute-release.yml`.
- No `lts` branch in the promotion flow. The `lts` git branch is archived.

**All PRs target `testing`.** Never target `main` or `lts` directly.
**Flow is one-way: `testing → main`.** Never merge `main → testing` manually.

## Promotion flow (`testing→main`)

`promote-testing-to-main.yml` maintains an always-open `auto/promote-testing-to-main` PR targeting `main`. Merging it cuts a release — see `docs/skills/release.md`.

1. PRs squash-merge to `testing`.
2. `promote-testing-to-main.yml` fires on push to `testing` and daily at 04:00 UTC.
3. Promote workflow compares `testing` vs `main` trees; rebuilds the squash branch if different.
4. Promotion PR enters the merge queue (ruleset 17070416 on `main`). `Lint & syntax` is the only gate check.
5. On merge, `execute-release.yml` fires on `push: main`, detects `"^chore: promote testing to main"`, skopeo-copies `:testing` → `:stable`.

**The promotion PR is squash-merge by design** — `reusable-promote-squash.yml` rebuilds the branch fresh from `main` on every run. Do not manually merge it.
**PRs touching `.github/workflows/` require `--admin` bypass** — CODEOWNERS blocks merge queue entry for workflow file changes.

## `stream_name` — how tags are determined

The 3 callers delegate entirely to `projectbluefin/actions/.github/workflows/reusable-build.yml@v1`. The key input is `stream_name`:

```yaml
stream_name: testing
```

| `stream_name` | Tags published |
|---|---|
| `testing` | `testing`, `testing-YYYYMMDD` |
| `stable` | `stable`, `stable-YYYYMMDD` |

There is no separate `publish: false` gate. Callers always publish when they run. On PRs, the `detect-changes` job may skip the build entirely if no image-relevant files changed.

## Event truth table

| Event | Ref | Tags published | Notes |
|---|---|---|---|
| `push` | `testing` | `testing`, `testing-YYYYMMDD` | normal CI after merge |
| `push` | `main` | `:stable` (via execute-release.yml) | only on promotion squash commit |
| `workflow_dispatch` | `testing` | `testing`, `testing-YYYYMMDD` | manual re-run |
| `pull_request` | `testing` | nothing | CI only; detect-changes may skip build entirely |
| `merge_group` | `main` | nothing | CI only |

## Centralized CI — `projectbluefin/actions`

Common CI/CD logic lives in reusable GitHub Actions at **https://github.com/projectbluefin/actions** (`@v1`).

### Reusable workflow used by bluefin-lts callers

`projectbluefin/actions/.github/workflows/reusable-build.yml@v1`

Inputs used by each caller:
- `brand_name` — image name (`bluefin-lts`, `bluefin-lts-hwe`, `bluefin-lts-hwe-nvidia`)
- `stream_name` — `testing` or `lts`
- `image_flavors` — `'["main"]'`
- `architecture` — `'["x86_64"]'`

### HWE and Nvidia kernel selection

HWE (`bluefin-lts-hwe`) and Nvidia (`bluefin-lts-hwe-nvidia`) use the **Fedora CoreOS stable** kernel, not the CentOS kernel. The Justfile resolves the current Fedora CoreOS stable version at build time:

```bash
skopeo inspect docker://quay.io/fedora/fedora-coreos:stable
# → derives Fedora version (e.g., 44) → selects coreos-stable-44 akmods
```

This means HWE/Nvidia kernels automatically track upstream as CoreOS advances Fedora versions — no manual pin bumps needed. Set `COREOS_STABLE_VERSION=NN` to override for testing.

Regular builds (`bluefin-lts`) use `centos-10` akmods and the CentOS Stream kernel.

### Shared composite actions in bluefin-lts

| Action | Where used | LTS-specific override |
|---|---|---|
| `bootc-build/validate-pr` | `pr-testsuite.yml` | `shellcheck-glob: "build_scripts/**/*.sh"` (lts uses `build_scripts/`, not `build_files/`) |
| `bootc-build/detect-changes` | `build-regular.yml`, `build-gdx.yml`, `build-regular-hwe.yml` | filters for `build_scripts/**` and `image-versions.yaml` |
| `bootc-build/sign-and-publish` | called internally by `reusable-build.yml@v1` | `signing-mode: keyless` |

## Schedule ownership

`promote-testing-to-main.yml` is the only scheduled workflow — daily at `0 4 * * *`. Do not add `schedule:` triggers to the build callers.

## Renovate auto-merge pipeline

`renovate-automerge.yml` triggers on `workflow_run: completed: "PR Validation — testsuite"` and only proceeds when `conclusion == 'success'`. `pr-testsuite` is lint-first, so it completes quickly and drives the bot flow.

Flow:
1. Renovate/Mergeraptor opens a PR against `testing`.
2. `renovate-automerge.yml` reacts to successful PR validation and calls `reusable-renovate-automerge.yml@v1`.
3. Merged bot changes land on `testing`; the daily promote workflow carries them to `main`.

**Required status check** (ruleset 4940669): `Lint & syntax` only. Builds are informational.

### Renovate automerge pitfalls

**All PRs target `testing`.** Renovate must target `testing`, not `main`.

**Never add `projectbluefin/actions` refs to the automerge `pin` rule.** The `matchUpdateTypes: ["pin"]` Renovate rule generates PRs that SHA-pin `@v1` managed tags to commit hashes. The `no-sha-pins-for-internal-actions` pre-commit hook rejects those for `projectbluefin/actions` permanently (exit 1). The fix is to exclude `projectbluefin/actions` refs:

```json
{
  "description": "Never SHA-pin projectbluefin/actions refs — use @v1 managed tags",
  "matchManagers": ["github-actions"],
  "matchDepNames": ["/^projectbluefin\/actions/"],
  "pinDigests": false,
  "enabled": false
}
```

If a stuck `chore(deps): pin dependencies` PR appears targeting `projectbluefin/actions`, close it — it can never pass lint. Add the rule above to `renovate.json` to prevent recurrence.

`projectbluefin/testsuite` uses `@v1` in `run-testsuite.yml`. The testsuite repo's `update-v1-tag.yml` workflow force-pushes the `v1` tag to HEAD on every merge to main — consumers always get the latest fixes without manual SHA bumps. Do not SHA-pin this ref; Renovate is disabled for it.

### projectbluefin/* refs — tag and pin policy

| Ref | Policy | Why |
|---|---|---|
| `projectbluefin/actions` | `@v1` managed tag — never SHA-pin | `no-sha-pins-for-internal-actions` pre-commit hook blocks SHA pins; Renovate is disabled for this ref |
| `projectbluefin/bonedigger` | `@v1` managed tag — never SHA-pin | Convention; no hook enforces this, but managed tags are the factory standard |
| `projectbluefin/testsuite` | `@v1` managed tag — never SHA-pin | `update-v1-tag.yml` in the testsuite repo force-pushes `v1` to HEAD on every main push; `no-sha-pins-for-internal-actions` hook blocks SHA pins; Renovate is disabled for this ref |

SHA-pinning `projectbluefin/actions` or `projectbluefin/testsuite` triggers `Lint & syntax` failure (the `no-sha-pins-for-internal-actions` hook — regex: `uses:.*projectbluefin/(actions|testsuite).*@[0-9a-f]{40}`). SHA-pinning `projectbluefin/bonedigger` is not caught by any hook but is wrong by convention.

### Handling stale Renovate SHA-bump branches after a bulk @v1 conversion

After merging a bulk PR that converts `projectbluefin/actions` SHA pins → `@v1`, Renovate's in-flight SHA-bump branch becomes stale: it tries to replace `@v1` with a specific SHA (going backwards). Fix:

```bash
git fetch origin
git checkout -B renovate/projectbluefinactions origin/main
git push origin renovate/projectbluefinactions --force
```

This resets the branch to main (empty diff). The open Renovate PR will show no changes and can be closed. Renovate will not re-open it since there are no SHA pins left to track.

**Required status check** (ruleset 4940669): `Lint & syntax` only. Builds are informational.

### Renovate common image tracking — critical pattern

`ghcr.io/projectbluefin/common` delivers first-party fixes (e.g. `rechunker-group-fix`, boot services) that are **safety-critical** for users. These must land in `:testing` automatically without human intervention.

### Cosign verification for base images

bluefin-lts verifies `common` and `brew` signatures before every build using vendored public keys in `keys/`.

| File | Key for |
|---|---|
| `keys/projectbluefin-common.pub` | `ghcr.io/projectbluefin/common` |
| `keys/ublue-os-brew.pub` | `ghcr.io/ublue-os/brew` |

`just verify-container` handles auto-install of cosign v3+ if the runner ships an older version. Verification is fatal in CI. Skip locally with `SKIP_BASE_VERIFY=1` (only works when `CI` is not `true`).

**cosign self-install bootstrap:** when the runner's cosign is pre-v3, `verify-container` downloads the pinned binary from GitHub Releases. The download is verified with `sha256sum` against the `.sha256` file published alongside the binary. Without this check the verification chain is circular — we would trust cosign because we downloaded it, which is the same supply-chain problem cosign is meant to prevent. Use `mktemp` for the install path to avoid concurrent-build races on shared runners.

When a key rotation occurs: update the `.pub` file in `keys/` via PR with justification, then retry the build.

**Pattern discovery:** A cosign signing regression in `common` was caught by `bluefin` CI (`no signatures found`) but went undetected by LTS because LTS had no signature verification. This is the canonical reason bluefin-lts must mirror bluefin's verification patterns — silent acceptance of unsigned images launders a potentially compromised image through the LTS signing pipeline.

`ghcr.io/projectbluefin/common` delivers first-party fixes (e.g. `rechunker-group-fix`, boot services) that are **safety-critical** for users. These must land in `:testing` automatically without human intervention.

**The right configuration (`renovate.json5`):**

1. **Custom manager for `image-versions.yaml`** — Renovate needs a regex manager to discover the `image: / tag: / digest:` block. Without it, common is invisible to Renovate:
```json5
{
  customType: 'regex',
  managerFilePatterns: ['/^image-versions\\.yaml$/'],
  matchStrings: [
    'image: (?<packageName>[^\\s]+)\\n\\s+tag: (?<currentValue>[^\\s]+)\\n\\s+digest: (?<currentDigest>sha256:[a-f0-9]+)',
  ],
  datasourceTemplate: 'docker',
  versioningTemplate: 'docker',
},
```

2. **`automerge: true` + `schedule: "at any time"`** for common — removes the default weekly delay from `config:best-practices`:
```json5
{
  "matchPackageNames": ["ghcr.io/projectbluefin/common"],
  "automerge": true,
  "schedule": ["at any time"]
},
```

**Never use `"enabled": false` for common** — this silently drops all critical fixes without any PR. The rechunker-group-fix was stuck in common for >2 days before manual intervention (issue ublue-os/bluefin-lts#918).

## Release pipeline pitfalls

**`org.opencontainers.image.revision` is the CentOS base SHA, not the LTS repo SHA.**
The label is inherited from `quay.io/centos-bootc/centos-bootc:c10s`. Never compare it to a `projectbluefin/bluefin-lts` commit SHA. The `resolve` job captures `locked_main_sha` from the GitHub API separately for the SHA guard and `update-lts-branch`.

**GitHub Actions transitive failure propagation.**
When a transitive ancestor fails (e.g. `run-upgrade-test`), GitHub skips all downstream jobs — even ones that only `needs:` a job that succeeded. Jobs after `promote` must use `if: always() && needs.X.result == 'success'`, not just `if: needs.X.result == 'success'`.

**`continue-on-error: true` is not valid on `uses:` jobs.**
actionlint rejects it. Make a job non-blocking by using `if: always() && ...` conditions on the jobs that depend on it.

**SHA guard fires if `main` advances during the upgrade-test window (~10 min).**
Re-run the promote workflow once main is quiet: `gh workflow run "Promote testing to main" --repo projectbluefin/bluefin-lts`

**Branch protection on `main`:** Required check `Lint & syntax` + linear history enforced. Matches `projectbluefin/bluefin`.

## Release-generation pitfalls

- `workflow_run` chaining does not propagate from `GITHUB_TOKEN`-dispatched workflows reliably enough for LTS release generation.
- `pr-validate.yml` in `projectbluefin/testsuite` is NOT a reusable workflow (no `workflow_call`). Never call it with `uses:`; it is the testsuite's own linter.

### bluefin vs bluefin-lts quick reference

These repo-local differences are the ones AI edits most often miss:

| Concern | bluefin default | bluefin-lts |
|---|---|---|
| Build shell path | `build_files/**/*.sh` | `build_scripts/**/*.sh` |
| Version file | `image-versions.yml` | `image-versions.yaml` |
| detect-changes filter | shared defaults often assume bluefin paths | always pass explicit `filters:` in `build-regular.yml` and `build-dx.yml` |
| PR shellcheck override | default action glob | `shellcheck-glob: "build_scripts/**/*.sh"` in `pr-testsuite.yml` |

If you copy workflow snippets from bluefin, translate those paths before saving.

### detect-changes filter override

bluefin-lts uses different paths from bluefin. **Always pass the `filters` input** when using detect-changes here:

```yaml
- uses: projectbluefin/actions/bootc-build/detect-changes@v1
  id: detect
  with:
    filters: |
      image:
        - 'Containerfile'
        - 'build_scripts/**'
        - 'system_files/**'
        - 'system_files_overrides/**'
        - 'image-versions.yaml'
        - 'Justfile'
      nvidia:
        - 'Containerfile'
```

Using the default (bluefin paths: `build_files/**`, `image-versions.yml`) would silently skip builds when real image changes land.

**Always include `system_files_overrides/**`** — variant-specific system files (Nvidia presets, VS Code hooks) live here. Without it, changes to `system_files_overrides/nvidia/` do not trigger the nvidia build on PRs. This gap caused a real missed trigger that was fixed in PR #225.

### validate-pr glob override

Default `shellcheck-glob` watches `build_files/**/*.sh`. LTS must override:

```yaml
- uses: projectbluefin/actions/bootc-build/validate-pr@v1
  with:
    shellcheck-glob: "build_scripts/**/*.sh"
```

The same `build_scripts/` + `image-versions.yaml` distinction should stay consistent in `AGENTS.md`, `.github/CODEOWNERS`, and `skill-drift.yml`.

## Rechunker — chunka@v1 (projectbluefin/actions)

Rechunking is handled internally by `projectbluefin/actions/.github/workflows/reusable-build.yml@v1`. The local `reusable-build-image.yml` was deleted in PR #73.

**`force-compression: true`:** LTS uses CentOS Stream 10, which must migrate existing registry layers from `gzip` to `zstd:chunked`. Fedora consumers (bluefin) leave this at the default `false` because their images are already `zstd:chunked`.

**Rechunk is skipped for `stream_name == testing`** (on-push builds to `testing`). Only production builds (`stream_name: stable`) rechunk.

**What the action does internally** (reference only — do not duplicate inline):
- `buildah build` with upstream `Containerfile.splitter` at the pinned chunkah SHA
- Key flags: `--prune /sysroot/`, `--max-layers 128`, `--label ostree.commit-`, `--label ostree.final-diffid-`
- `-v $(pwd):/run/src --security-opt=label=disable` for buildah < v1.44 bind-mount stability
- `sudo podman save | podman load` to transfer rechunked image from root (buildah) to user (podman) storage

**Do not reproduce the inline buildah invocation.** All details live in `projectbluefin/actions/bootc-build/chunka/action.yml`. If a flag needs changing, update the shared action.

## GHCR Package Access — always use `github.token`, never custom PATs

**Policy: Custom tokens (PATs, `PACKAGES_TOKEN`, etc.) are an antipattern in this project.**
When a workflow can't access a package, fix the package permissions — do not create a token.

All CI steps use only `github.token` (or `secrets.GITHUB_TOKEN`) for GHCR access.
If you see a `PACKAGES_TOKEN` or any other secret used for registry login, that is a bug.

### Required package configuration (org admin, one-time setup)

Three GHCR packages must be linked to `projectbluefin/bluefin-lts` and grant Actions write access:

| Package | Settings URL |
|---|---|
| `bluefin-lts` | https://github.com/orgs/projectbluefin/packages/container/bluefin-lts/settings |
| `bluefin-lts-hwe` | https://github.com/orgs/projectbluefin/packages/container/bluefin-lts-hwe/settings |
| `bluefin-lts-hwe-nvidia` | https://github.com/orgs/projectbluefin/packages/container/bluefin-lts-hwe-nvidia/settings |

On each settings page:
1. **Connected repository** → set to `projectbluefin/bluefin-lts`
2. **Manage Actions access** → "Add repository" → `projectbluefin/bluefin-lts` → **Write**

Once done, `github.token` from any `bluefin-lts` workflow has full package read/write — no PAT needed.

> **Note:** `bluefin-lts-hwe-nvidia` is a new package (created 2026-06-14, PR #225). New GHCR packages in an org
> are **private by default** — `skopeo list-tags` returns `name unknown` until the package is published AND
> linked to the repo. Link it via the settings page above. `bluefin-lts` may still be linked to
> `projectbluefin/bluefin` rather than `bluefin-lts` — verify and correct if GHCR pushes fail with `DENIED`.

## SBOM rules

- Generate/attest SBOMs **only** when `inputs.publish` is true.
- All SBOM steps must keep `continue-on-error: true`.
- Failed SBOM attestation must never block image publishing.

### SBOM permission gotcha

`reusable-build.yml` calls `sudo -E just gen-sbom` which creates `sbom_out/` **owned by root**.
The subsequent `sign-and-publish` step runs without `sudo` and fails with `permission denied` on `sbom_out/$IMAGE/sbom.json`.

**Fix is in the Justfile `gen-sbom` recipe:** after syft writes the file, ownership is returned to the invoking user:
```bash
chown -R "${SUDO_UID:-$(id -u)}:${SUDO_GID:-$(id -g)}" "sbom_out/" 2>/dev/null || true
```

If you ever touch `gen-sbom` in the Justfile, preserve this line.

## Condition quick reference

| Step/job | Condition |
|---|---|
| SBOM steps | `inputs.publish` + `continue-on-error: true` |
| Rechunk (chunkah) | `inputs.rechunk && inputs.publish` |
| Load/Login/Push/Cosign/Outputs/Manifest push | `inputs.publish` |
| manifest signing (inline in manifest job) | `inputs.publish` |

If nothing is pushed, nothing should sign.

---

## uupd install — COPR removed, use GitHub releases

**Context:** The `ublue-os/packages` COPR epel-10 chroot was removed. Any build using the old COPR repo will get a 404 and fail. Do not restore that pattern.

**Fix:** Install `uupd` from its GitHub release tarball. Version is pinned in `image-versions.yaml`:
```yaml
downloads:
  # renovate: datasource=github-releases depName=ublue-os/uupd
  uupd: "v1.4.0"
```

In `build_scripts/20-packages.sh`:
```bash
# yq is NOT available in the CentOS build container — use grep/sed
UUPD_VERSION=$(grep '^\s*uupd:' /run/context/image-versions.yaml | sed 's/.*"\(.*\)".*/\1/')
curl -fsSL "https://github.com/ublue-os/uupd/releases/download/${UUPD_VERSION}/uupd_Linux_x86_64.tar.gz" \
    | tar -xzf - -C /usr/bin uupd
chmod 0755 /usr/bin/uupd
```

The tarball ships binary only — fetch service files separately:
```bash
UUPD_RAW="https://raw.githubusercontent.com/ublue-os/uupd/${UUPD_VERSION}"
curl -fsSL "${UUPD_RAW}/uupd.service" -o /usr/lib/systemd/system/uupd.service
curl -fsSL "${UUPD_RAW}/uupd.timer"   -o /usr/lib/systemd/system/uupd.timer
```

**Three rules from this failure:**
1. `yq` is not in the CentOS Stream build container. Use `grep`/`sed`/`awk`.
2. `image-versions.yaml` must be in the context stage (`COPY image-versions.yaml /image-versions.yaml` in Containerfile).
3. `build_scripts/40-services.sh` must run **after** the service files exist — install order matters.

---

## PR-based release gate model

**Design:** The always-open `auto/promote-testing-to-main` PR is the release gate. It auto-merges when all gate checks pass — no human approval required. Gate checks run automatically after each promotion update.

**Key GITHUB_TOKEN limitations (both apply here):**
1. `GITHUB_TOKEN` pushes to a branch do NOT fire `pull_request: synchronize` events — GitHub blocks this to prevent loops.
2. `GITHUB_TOKEN` cannot trigger `workflow_dispatch` events via the API (HTTP 403).

**Solution:** Inline the gate as a `gate` job inside `promote-testing-to-main.yml` rather than dispatching separately:
```yaml
jobs:
  promote:
    outputs:
      sync_needed: ${{ steps.compare.outputs.sync_needed }}
      pr_number: ${{ steps.upsert.outputs.pr_number }}
      testing_sha: ${{ steps.compare.outputs.testing_sha }}
    ...

  gate:
    needs: [promote]
    if: needs.promote.outputs.sync_needed == 'true'
    uses: projectbluefin/actions/.github/workflows/reusable-release-gate.yml@main
    with:
      pr_number: ${{ needs.promote.outputs.pr_number }}
      head_sha: ${{ needs.promote.outputs.testing_sha }}
      ...
```

**reusable-release-gate.yml inputs:** `pr_number` and `head_sha` are optional overrides. When provided, they replace `context.payload.pull_request?.number` and `github.event.pull_request.head.sha` respectively — enabling the gate to run outside a pull_request event context.

**Gate output on PR #125:** Sticky comment with `<!-- release-status-marker -->` is posted/updated on the promotion PR. Labels `release/ready` or `release/blocked` are auto-applied.

**E2E gate:** The gate checks for a `post-testing-e2e` workflow run on the PR's head SHA. When there is none (fresh image builds), the e2e check fails and the PR is labeled `release/blocked`. This is expected — maintainers can review and merge anyway via admin bypass.

---

## execute-release.yml — startup_failure diagnosis and fix

### Root cause

`execute-release.yml` calls `reusable-release.yml@main` from the `release-notes` job. That reusable workflow's nested `image-release` job has `permissions: { contents: write, actions: read }`. GitHub validates ALL permissions requested by nested jobs against the caller's permission grant at **workflow startup**, before any code runs. If the caller job does not grant a permission the callee requests, the entire workflow run gets `startup_failure` with no log output.

Error (visible ONLY by fetching the Actions web page, not via API/CLI):
```
Error calling workflow 'reusable-release.yml@main'.
The nested job 'image-release' is requesting 'actions: read', but is only allowed 'actions: none'.
```

**Fix:** Add `actions: read` to the `release-notes` job permissions block.

```yaml
  release-notes:
    permissions:
      actions: read       # required by reusable-release.yml's image-release nested job
      contents: write
      id-token: write
      packages: read
    uses: projectbluefin/actions/.github/workflows/reusable-release.yml@main
```

### How to diagnose startup_failure in GitHub Actions

GitHub API endpoints (`/jobs`, `/logs`) return nothing for `startup_failure` runs. `gh run view` gives only a generic "workflow file issue" message. Open the run URL directly in a browser and search for "requesting" or "is not allowed" in the page. The error format is:

```
Error calling workflow 'reusable-X.yml@main'.
The nested job 'Y' is requesting 'actions: read', but is only allowed 'actions: none'.
```

`gh run view <RUN_ID> --repo projectbluefin/bluefin-lts` will show `startup_failure` status but no log. The web UI is the only place the specific permission mismatch is shown.

### YAML syntax gotcha in `if:` conditions with colons in strings

If a commit message pattern contains `: ` (colon-space), the `if:` condition will fail YAML parsing:

```yaml
# BROKEN — ': ' in single-quoted string breaks YAML scalar
if: startsWith(github.event.head_commit.message, 'chore: promote testing to main')

# CORRECT — wrap entire condition in double quotes
if: "startsWith(github.event.head_commit.message, 'chore: promote testing to main')"
```

### actionlint [expression] rule — untrusted inputs in run: steps

actionlint flags `github.event.head_commit.message` (and other user-controlled inputs) when interpolated directly into a `run:` shell script. It is safe in `if:` conditions because those are evaluated by GitHub's expression engine, not the shell.

```yaml
# BROKEN — actionlint [expression] error, injection risk
- run: |
    MSG="${{ github.event.head_commit.message }}"

# CORRECT — pass through env var
- env:
    COMMIT_MSG: ${{ github.event.head_commit.message }}
  run: |
    if echo "$COMMIT_MSG" | grep -q "^chore:"; then ...

# ALSO CORRECT — if: conditions are not shell, no injection risk
  if: "startsWith(github.event.head_commit.message, 'chore: promote testing to main')"
```

### execute-release.yml trigger change (push vs pull_request)

The `pull_request: closed` trigger was replaced with `push: branches: [main]` because:
- Bot-authored PRs that modify `.github/workflows/` via GITHUB_TOKEN cannot fire `pull_request` events (GitHub security restriction).
- Push events fire for all merges including admin force-merges.
- A `check-trigger` job with the `if: startsWith(...)` condition gates the actual release jobs so non-promotion pushes are no-ops.

---

## E2E known issues — QEMU environment artifacts

These units fail in the QEMU CI VM but are harmless on real hardware.
The fix in each case is to add `systemd.mask=<unit>` to `KERNEL_ARGS` in
`projectbluefin/testsuite/.github/workflows/e2e.yml`.

| Unit | Why it fails in QEMU | Fix PR |
|------|---------------------|--------|
| `systemd-udev-settle.service` | Waits for udev to settle real hardware; times out (~125s) in QEMU with no physical devices. Manifests as `"No failed systemd units at boot"` smoke test failure. | projectbluefin/testsuite#419 |
| `bootloader-update.service` | Updates the EFI bootloader on boot; fails in QEMU VMs that have no EFI boot entry to update. Appears in VM serial log as `FAILED`. Currently not caught by the smoke test assertion — no open fix PR. |

**After a testsuite fix merges**, `run-testsuite.yml` picks it up immediately — `@v1` is automatically advanced to HEAD by the testsuite's `update-v1-tag.yml`. No Renovate SHA bump PR needed. Remove any temporary KERNEL_ARGS mask in the testsuite if the fix makes it obsolete.

**`run-testsuite.yml` uses `@v1`, not a SHA pin.** Do not convert it to a SHA — the `no-sha-pins-for-internal-actions` hook blocks SHA pins on both `projectbluefin/actions` and `projectbluefin/testsuite`, and Renovate is disabled for this ref.

**`test_ref: v1` must be explicitly passed.** `run-testsuite.yml` must pass `test_ref: v1` to the reusable testsuite workflow, otherwise the workflow checks out test code from `main` even though the workflow itself is pinned to `@v1`. This causes bluefin-lts to be gated by unreleased test changes and is the most common cause of E2E failures after a `@v1` migration.

```yaml
# run-testsuite.yml — required
with:
  image: ${{ inputs.image }}
  suites: ${{ inputs.suites }}
  test_ref: v1   # must match the workflow tag — omitting this defaults to main
```

**`common_dconf` E2E suite requires a gschema override for `enabled-extensions`.** The `custom-command-list extension is in distribution defaults` scenario checks that bundled GNOME extensions appear in the `org.gnome.shell` gsettings schema default. Bundling an extension in `system_files/usr/share/gnome-shell/extensions/` is not enough — it must also be listed in a gschema override:

```
system_files/usr/share/glib-2.0/schemas/zz1-bluefin-lts-shell.gschema.override
[org.gnome.shell]
enabled-extensions = ['<ext1>', '<ext2>', ...]
```

Include only extensions that are physically present in `system_files/usr/share/gnome-shell/extensions/`. Extensions that come from `common` or packages should not be listed here.

---

## Trivy scan FATAL — CentOS 10 CPE indices missing

**Symptom:** All three build jobs (`Build Bluefin LTS`, `Build Bluefin LTS HWE`, `Build Bluefin Nvidia`) fail at the `image (main, …, testing, x86_64)` step with exit code 1 and no obvious container build error. The actual error is Trivy crashing at the very end of the job (after a successful container build):

```
FATAL  Fatal error  run error: image scan error: … unable to find CPE indices.
See https://github.com/aquasecurity/trivy-db/issues/435
```

**Root cause:** Trivy 0.70.x exits 1 with `FATAL` when its database has no CPE index entries for a new OS family (CentOS Stream 10). The `exit-code: '0'` Trivy parameter only suppresses non-zero exit when *vulnerabilities are found* — it does **not** suppress exits caused by Trivy's own DB crash.

The `bootc-build/scan-image@v1` action in `projectbluefin/actions` did not have `continue-on-error: true` on the Trivy steps, so a Trivy FATAL kills the entire build job.

**Fix:** `projectbluefin/actions` PR #201:
- `continue-on-error: true` on both Trivy scan steps (SARIF + JSON)
- Guard Python summarize step against missing `trivy-results.json`

**After actions PR #201 merges:** A maintainer must retag `v1` in `projectbluefin/actions`:
```bash
git tag -f v1 <merge-commit-sha>
git push origin v1 --force
```
All consuming repos (`bluefin-lts`, `bluefin`, `dakota`) pick up the fix immediately via `@v1`.

**Note:** The dracut POSTTRANS failures (`error: rpm-ostree kernel-install: … Invalid cross-device link`) in `kernel-swap.sh` are **non-fatal warnings** — dnf exits 0 despite them and the build continues past them. They appear in logs but do not kill the build. PR #174 adds `export DRACUT_TMPDIR=/boot` as a belt-and-suspenders fix but the primary blocker is the Trivy issue above.

## changelogs.py — OCI manifest diff changelog

`changelogs.py` (`.github/`) generates per-package changelogs by comparing OCI image manifests via skopeo between published container tags. It is called by `reusable-release.yml` from the consumer repo's `.github/` directory.

**This tool is different from the two changelog tools in `projectbluefin/actions`:**

| Tool | Input | Output |
|---|---|---|
| `bootc-build/generate-release-notes` | git commit history | Conventional Commits changelog |
| `bootc-build/create-release` (`sbom_diff.py`) | SPDX SBOM artifacts | Notable package version table |
| `changelogs.py` (this repo) | OCI manifests via skopeo | Full RPM diff between image tags |

**Drift warning:** `bluefin-lts/changelogs.py` (1176 lines, config-driven via `changelog_config.yaml`) and `bluefin/changelogs.py` (534 lines, hardcoded globals) have diverged. Each repo maintains its own copy. Tracked for centralization in `projectbluefin/common#707` (`bootc-build/generate-manifest-changelog` action proposed).

**When modifying `changelogs.py`:**
- Tests live in `tests/test_changelogs.py` (pytest, run via `.github/workflows/pytest.yml`)
- `MINIMAL_CONFIG` in the test file must mirror the production `changelog_config.yaml` schema exactly — divergence creates false-green tests where production code paths are never exercised
- Verify `sections` keys (`all`, `base`, `dx`, `nvidia`) and `templates` keys (including `changelog_format`) match `changelog_config.yaml`

## ublue-os → projectbluefin migration

For the complete implementation spec (script, service unit, timer unit, file paths,
build enablement, testing) see **[`docs/skills/migration.md`](migration.md)**.

### Signing policy — verified 2026-06-21

Inspected `/etc/containers/policy.json` on `ghcr.io/ublue-os/bluefin:lts` and `ghcr.io/projectbluefin/bluefin-lts:stable` — both images ship the **same** policy.json (from `projectbluefin/common`).

- `ghcr.io/ublue-os` → `sigstoreSigned` with key-based verification (ublue-os.pub)
- `ghcr.io/projectbluefin` → **not listed** → falls through to `""` catch-all → `insecureAcceptAnything`

`bootc switch --enforce-container-sigpolicy ghcr.io/projectbluefin/bluefin-lts:stable` succeeds on the old image (insecureAcceptAnything). The new image's own ongoing updates are also unverified by the current policy — adding a `sigstoreSigned` keyless entry for `ghcr.io/projectbluefin` is a separate hardening task.

### New LTS signing: keyless (OIDC/Fulcio)

New LTS images are signed via `projectbluefin/actions` `sign-and-publish` action with `signing-mode: keyless`. Verification uses:
```
cosign verify \
  --certificate-identity-regexp="https://github.com/projectbluefin/(bluefin|bluefin-lts|dakota|common|aurora|actions)/.github/workflows/" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  ghcr.io/projectbluefin/<image>:<tag>
```
The `cosign.pub` files in both repos are identical but are **not used** for new LTS images — they are leftovers from before the switch to keyless.

### Migration service (ships in ublue-os/bluefin-lts)

A `bluefin-lts-migration.timer` + `bluefin-lts-migration.service` ships in the old image's weekly build. The service:
1. Checks for `/etc/bluefin-lts-migrated` stamp — exits 0 if present
2. Reads current image from `bootc status --format=json`
3. Exits 0 if already on `projectbluefin`; writes MOTD + exits 0 for arm64
4. Maps variant to new image (gdx→hwe-nvidia, dx+hwe→lts-hwe, dx→lts, hwe→lts-hwe, *→lts)
5. Writes `/etc/motd.d/50-bluefin-lts-migration` with next-reboot notice
6. Runs `bootc switch --enforce-container-sigpolicy <new-image>` — non-destructive until reboot
7. On success: touches stamp, disables timer; on failure: appends retry note to MOTD, exits 1

Timer retries daily (`OnUnitInactiveSec=24h`) until success. MOTD self-cleans on reboot (not present on new image). dx/gdx users see a `ujust devmode` note.

### Variant mapping (old → new)

| Old (ublue-os) | New (projectbluefin) | Notes |
|---|---|---|
| `bluefin-gdx:lts*` | `bluefin-lts-hwe-nvidia:stable` | dx/gdx: ujust devmode |
| `bluefin-dx:lts-hwe*` | `bluefin-lts-hwe:stable` | dx: ujust devmode |
| `bluefin-dx:lts*` | `bluefin-lts:stable` | dx: ujust devmode |
| `bluefin:lts-hwe*` | `bluefin-lts-hwe:stable` | |
| `bluefin:lts*` (incl. GNOME50) | `bluefin-lts:stable` | |
| arm64 | MOTD only, no switch | unsupported |

### ghost lab migration workflow

`bluefin-migration-test` and `migration-upgrade-test` Argo templates in the ghost lab are NOT suitable for LTS migration testing as-is. Known issues:
- `run-bootc-switch` hardcodes `--enforce-container-sigpolicy` with no override
- Golden disk cache keyed by tag only — all `lts`-tagged variants collide
- Tests backward (new→old) direction which adds irrelevant failure modes
- Weak target verification (substring, not digest)

Use `projectbluefin/actions/.github/workflows/migration-test.yml` via `workflow_dispatch` instead — it delegates to the testsuite and avoids these issues.

## countme: rpm-ostree-countme is broken on CentOS — replaced with dnf5 service

### Root cause

`rpm-ostree-countme.service` uses an old libdnf4 snapshot that cannot expand
shell-style variable syntax. EPEL 10's metalink URL requires this:

  metalink=https://mirrors.fedoraproject.org/metalink?repo=epel${releasever_minor:+-z}-${releasever}&arch=${basearch}

On CentOS, `releasever_minor` is intentionally undefined. dnf5 expands the
expression to empty → `epel-10` (correct). rpm-ostree's libdnf4 sends the literal
`${releasever_minor:+-z}` → HTTP 404.

Upstream: coreos/rpm-ostree#5464, projectbluefin/bluefin-lts#656

### Workaround (shipped in bluefin-lts)

- `rpm-ostree-countme.service` and `rpm-ostree-countme.timer` are **masked**
  in `build_scripts/40-services.sh`.
- `bluefin-lts-countme.service` + `bluefin-lts-countme.timer` are shipped in
  `system_files/usr/lib/systemd/system/` and enabled at build time.
- The service runs `dnf5 makecache` as root on a weekly schedule.
  dnf5 handles the variable expansion correctly and reads `NAME="Bluefin LTS"`
  from `/usr/lib/os-release` for the User-Agent, so pings are attributed
  correctly in Fedora/EPEL mirror logs.
- dnf5 countme cookie (`persistdir` per repo) enforces the 7-day window —
  the timer fires every 3 days (matching Fedora's `rpm-ostree-countme.timer`)
  so systems that are offline a few days still get counted within a week.

### ublue-os/countme badge

The `bluefin-lts` badge in `ublue-os/countme generate_badge_data.py` is
currently commented out ("centos countme data is broken"). Once data starts
flowing, open a PR there to re-enable it, then update the `ghcurl` line in
`build_scripts/90-image-info.sh` to use `bluefin-lts.json` instead of
`bluefin.json`.

## Merging PRs as repo admin

### Merge queue + CODEOWNERS blocks all PRs

`main` has a merge queue enabled. `gh pr merge --auto` has no effect when a merge queue is
active — it silently sets the GitHub auto-merge flag but the PR stays BLOCKED. PRs must enter
the queue explicitly, and the queue requires CODEOWNERS approval first.

CODEOWNERS has a `*` wildcard:
```
* @projectbluefin/maintainers
```
This catches **every** PR including docs-only. Before any PR can enter the queue,
`projectbluefin/maintainers` must approve. Since castrojo is the PR author and GitHub blocks
self-approval, all PRs get stuck.

**Fix as repo admin:**
```bash
gh pr merge <number> --admin --squash
```
The `--admin` flag bypasses branch protection, including CODEOWNERS and the merge queue.
Use squash — the ruleset only allows squash merges (attempts with `--merge` or `--rebase` fail).

**Diagnosis commands:**
```bash
# See why a PR is BLOCKED
gh pr view <number> --json mergeStateStatus,mergeable,reviewDecision

# Check ruleset (merge queue config, required approvals)
gh api repos/projectbluefin/bluefin-lts/rules/branches/main | python3 -c "import json,sys; [print(r['type'], json.dumps(r.get('parameters',{}))[:200]) for r in json.load(sys.stdin)]"
```

### Renovate PRs: rebasing

Renovate targets `testing`, not `main`. Its PRs accumulate all intermediate squash commits
from testing history, so a rebase onto current `testing` will replay many commits and hit
multiple conflicts. Common conflicts:

- `image-versions.yaml` — competing digest bumps; keep the **newer** (HEAD) digest
- `.github/workflows/run-testsuite.yml` — uses `@v1`; no SHA conflicts expected (Renovate is disabled for this ref)
- `.github/workflows/bonedigger.yml` — Renovate's pin-dependencies tries to SHA-pin this; **keep `@v1`** — bonedigger is an intentional managed tag, exempt from SHA pinning

Fastest resolution pattern when conflicts cascade:
```bash
while git diff --name-only --diff-filter=U | grep -q .; do
  for f in $(git diff --name-only --diff-filter=U); do
    git checkout --theirs "$f"
    git add "$f"
  done
  GIT_EDITOR=true git rebase --continue
done
```
Then manually fix `image-versions.yaml` if the brew/common digest was newer in HEAD than theirs.
