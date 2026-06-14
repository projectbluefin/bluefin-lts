---
name: bluefin-lts-ci-cd
description: >-
  CI/CD workflow map, publish logic, tag namespaces, and release pipeline for
  projectbluefin/bluefin-lts. Use when debugging build triggers, understanding stream_name tag
  routing, fixing the release pipeline, authoring new workflows, or investigating why images
  were not published. Contains critical pitfalls for cosign, GitHub Actions propagation, and
  lts branch management.
metadata:
  type: reference
---

# CI/CD

## Contents
- [Workflow map](#workflow-map)
- [Branches and tags](#branches-and-tags)
- [Promotion flow](#promotion-flow-mainlts)
- [stream_name routing](#stream_name--how-tags-are-determined)
- [Event truth table](#event-truth-table)
- [Centralized CI — projectbluefin/actions](#centralized-ci--projectbluefinaactions)
- [Schedule ownership](#schedule-ownership)
- [Renovate auto-merge pipeline](#renovate-auto-merge-pipeline)
- [Weekly release pipeline](#weekly-release-pipeline)
- [Release pipeline pitfalls](#release-pipeline-pitfalls)
- [GHCR Package Access](#ghcr-package-access--always-use-githubtoken-never-custom-pats)
- [SBOM rules](#sbom-rules)
- [Condition quick reference](#condition-quick-reference)

## Workflow map

| File | Role |
|---|---|
| `build-regular.yml` | caller for `bluefin-lts` |
| `build-regular-hwe.yml` | caller for `bluefin-lts-hwe` (HWE kernel) |
| `build-gdx.yml` | caller for `bluefin-gdx` (NVIDIA/AI) |
| `sync-main-to-testing.yml` | force-syncs `main → testing` on every push to `main`; thin caller to `projectbluefin/actions/reusable-sync-branches.yml@v1` |
| `promote-testing-to-main.yml` | maintains always-open `auto/promote-testing-to-main` PR (`main → lts`); calls `reusable-promote-squash.yml@v1` with `source_branch=main, target_branch=lts` |
| `execute-release.yml` | fires on promotion PR merge; cosign re-verify, skopeo `:testing` → `:lts`, fast-forward `lts`, GitHub release |
| ~~`sync-main-to-lts.yml`~~ | **deleted** — replaced by PR-as-gate promotion model |
| ~~`scheduled-lts-release.yml`~~ | **deleted** — releases cut by merging the promotion PR |
| ~~`generate-release.yml`~~ | **deleted** — release creation handled by `execute-release.yml` |
| ~~`lifecycle-caller.yml`~~ | **deleted** |
| `pr-testsuite.yml` | runs **`validate-pr@v1`** (just check, shellcheck, hadolint, pre-commit) + **e2e smoke** on every PR; only `Lint & syntax` is a required check |
| `pr-e2e.yml` | advisory PR E2E gate; composes `system_files/` changes on top of `bluefin-lts:testing` and runs smoke suite; non-blocking; only fires when image-relevant paths change |
| `pr-e2e-smoke.yml` | informational E2E smoke on every PR; always fails due to `ublue-os/` prefix mismatch in testsuite (issue #34, testsuite#412); never block merge on this |
| `run-testsuite.yml` | canonical wrapper for calling `projectbluefin/testsuite` — always call via this file, never call the testsuite `e2e.yml` directly; use `@main` (never SHA-pin — see below) |
| `renovate-automerge.yml` | auto-merges Renovate/mergeraptor PRs when pr-testsuite passes |
| `post-merge-e2e.yml` | runs E2E smoke+common suites after a successful build on `main`; informational only |
| `lifecycle-caller.yml` | issue and PR lifecycle automation (bonedigger pipeline via `projectbluefin/common`) |
| `skill-drift.yml` | warns on PRs that change CI/build/system files without updating docs/skills |
| `validate-renovate.yaml` | validates `.github/renovate.json5` on relevant PRs and pushes |
| ~~`build-dx.yml`~~ | **deleted** — no DX variant in LTS; GDX is the NVIDIA product |
| ~~`build-dx-hwe.yml`~~ | **deleted** — no DX HWE variant |
| ~~`build-gnome50.yml`~~ | **deleted 2026-05-30** — GNOME 50 is now the default |
| ~~`reusable-build-image.yml`~~ | **deleted** — replaced by `projectbluefin/actions/.github/workflows/reusable-build.yml@v1` |
| ~~`create-lts-pr.yml`~~ | **deleted 2026-05-30** — replaced by `sync-main-to-lts.yml` |

## Branches and tags

| Branch | Image | Tags | When |
|---|---|---|---|
| `main` | `bluefin-lts` | `testing`, `testing-YYYYMMDD` | every push/merge to `main` |
| `main` | `bluefin-lts-hwe` | `testing`, `testing-YYYYMMDD` | every push/merge to `main` |
| `main` | `bluefin-gdx` | `testing`, `testing-YYYYMMDD` | every push/merge to `main` |
| `lts` | `bluefin-lts` | `lts`, `lts-YYYYMMDD` | `workflow_dispatch` on `lts` only |
| `lts` | `bluefin-lts-hwe` | `lts`, `lts-YYYYMMDD` | `workflow_dispatch` on `lts` only |
| `lts` | `bluefin-gdx` | `lts`, `lts-YYYYMMDD` | `workflow_dispatch` on `lts` only |

`push` to `lts` does **not** trigger any build workflow (no `push: lts` trigger exists in any caller). The merge itself fires only `lifecycle-caller.yml`.

## Promotion flow (`main→lts`)

`promote-testing-to-main.yml` maintains an always-open `auto/promote-testing-to-main` PR targeting `lts`. Merging it cuts a release — see `docs/skills/release.md`.

**Critical:** The caller passes `source_branch: main` and `target_branch: lts`. Without these, the reusable workflow defaults to `testing → main`, trees are always identical, and no PR is ever created.

1. PRs squash-merge to `main`.
2. `sync-main-to-testing.yml` mirrors `main → testing`, triggering the promote workflow.
3. Promote workflow compares `main` vs `lts` trees; rebuilds squash branch if different.
4. Maintainers merge promotion PR (2 approvals required) → `execute-release.yml` fires → `:testing` copied to `:lts`.

**Never squash-merge the promotion PR** — breaks merge base for future promotions.
**Never merge `lts→main`.**

## `stream_name` — how tags are determined

The 3 callers delegate entirely to `projectbluefin/actions/.github/workflows/reusable-build.yml@v1`. The key input is `stream_name`:

```yaml
stream_name: ${{ github.ref == 'refs/heads/lts' && 'lts' || 'testing' }}
```

| `stream_name` | Tags published |
|---|---|
| `testing` | `testing`, `testing-YYYYMMDD` |
| `lts` | `lts`, `lts-YYYYMMDD` |

There is no separate `publish: false` gate. Callers always publish when they run. On PRs, the `detect-changes` job may skip the build entirely if no image-relevant files changed.

## Event truth table

| Event | Ref | Tags published | Notes |
|---|---|---|---|
| `push` | `main` | `testing`, `testing-YYYYMMDD` | normal CI after merge |
| `push` | `lts` | nothing | no build callers trigger on lts push |
| `workflow_dispatch` | `main` | `testing`, `testing-YYYYMMDD` | manual re-run |
| `workflow_dispatch` | `lts` | `lts`, `lts-YYYYMMDD` | triggered by `execute-release.yml` on promotion merge |
| `pull_request` | `main` | nothing | CI only; detect-changes may skip build entirely |
| `merge_group` | `main` | nothing | CI only |

## Centralized CI — `projectbluefin/actions`

Common CI/CD logic lives in reusable GitHub Actions at **https://github.com/projectbluefin/actions** (`@v1`).

### Reusable workflow used by bluefin-lts callers

`projectbluefin/actions/.github/workflows/reusable-build.yml@v1`

Inputs used by each caller:
- `brand_name` — image name (`bluefin-lts`, `bluefin-lts-hwe`, `bluefin-gdx`)
- `stream_name` — `testing` or `lts`
- `image_flavors` — `'["main"]'`
- `architecture` — `'["x86_64"]'`

### HWE and GDX kernel selection

HWE (`bluefin-lts-hwe`) and GDX (`bluefin-gdx`) use the **Fedora CoreOS stable** kernel, not the CentOS kernel. The Justfile resolves the current Fedora CoreOS stable version at build time:

```bash
skopeo inspect docker://quay.io/fedora/fedora-coreos:stable
# → derives Fedora version (e.g., 44) → selects coreos-stable-44 akmods
```

This means HWE/GDX kernels automatically track upstream as CoreOS advances Fedora versions — no manual pin bumps needed. Set `COREOS_STABLE_VERSION=NN` to override for testing.

Regular builds (`bluefin-lts`) use `centos-10` akmods and the CentOS Stream kernel.

### Shared composite actions in bluefin-lts

| Action | Where used | LTS-specific override |
|---|---|---|
| `bootc-build/validate-pr` | `pr-testsuite.yml` | `shellcheck-glob: "build_scripts/**/*.sh"` (lts uses `build_scripts/`, not `build_files/`) |
| `bootc-build/detect-changes` | `build-regular.yml`, `build-gdx.yml`, `build-regular-hwe.yml` | filters for `build_scripts/**` and `image-versions.yaml` |
| `bootc-build/sign-and-publish` | called internally by `reusable-build.yml@v1` | `signing-mode: keyless` |

## Schedule ownership

`release-reminder.yml` is the only scheduled workflow — posts a reminder on the promotion PR after 7 days open. Do not add `schedule:` triggers to the build callers.

## Renovate auto-merge pipeline

`renovate-automerge.yml` triggers on `workflow_run: completed: "PR Validation — testsuite"` and only proceeds when `conclusion == 'success'`. `pr-testsuite` is **lint-only** (COPR guard + validate-pr — no E2E smoke), so it completes in ~10 min and drives automerge reliably.

Flow:
1. Renovate opens PR → `pr-testsuite.yml` runs lint (~10 min)
2. `renovate-automerge.yml` triggers on `workflow_run` success → calls `reusable-renovate-automerge.yml@v1`
3. PR merges to `main` → build workflows fire on `push: main` → `:testing` published

**Required status check** (ruleset 4940669): `Lint & syntax` only. Builds are informational.

### Renovate automerge pitfalls

**`base_branch` must be set explicitly.** `reusable-renovate-automerge.yml@v1` defaults `base_branch` to `testing`. All bluefin-lts Renovate PRs target `main`. Without the override the automerge workflow logs `No open Renovate/Mergeraptor PR found for SHA … on base testing — skipping` and never merges anything.

```yaml
# renovate-automerge.yml — required
jobs:
  automerge:
    uses: projectbluefin/actions/.github/workflows/reusable-renovate-automerge.yml@v1
    with:
      head_sha: ${{ github.event.workflow_run.head_sha }}
      base_branch: main   # ← must be explicit; default is 'testing'
```

**Never add `projectbluefin/` refs to the automerge `pin` rule.** The `matchUpdateTypes: ["pin"]` Renovate rule generates PRs that SHA-pin `@v1`/`@main` managed tags to commit hashes. The `no-sha-pins-for-internal-actions` pre-commit hook then rejects them permanently (exit 1). The fix is to exclude all `projectbluefin/` refs entirely:

```json
{
  "description": "Never SHA-pin projectbluefin/ refs — use @v1/@main managed tags",
  "matchManagers": ["github-actions"],
  "matchDepNames": ["/^projectbluefin\\//"],
  "pinDigests": false,
  "enabled": false
}
```

If a stuck `chore(deps): pin dependencies` PR appears targeting `projectbluefin/actions`, close it — it can never pass lint. Add the rule above to `renovate.json` to prevent recurrence.

### projectbluefin/* refs — always use managed tags, never SHA-pin

All `projectbluefin/` refs in `.github/workflows/` must use managed tags (`@v1` or `@main`). **Never SHA-pin any `projectbluefin/` repo**, including `projectbluefin/testsuite`.

- **`projectbluefin/actions`** → `@v1`
- **`projectbluefin/testsuite`** → `@main`
- SHA-pinned internal refs trigger the `validate-pr` action's tag checker, causing `Lint & syntax` to fail with exit code 1 — this blocks the Renovate automerge pipeline entirely
- AGENTS.md explicitly exempts `projectbluefin/` refs from the SHA-pin requirement: *"projectbluefin/ refs (@v1, @main) are intentional managed tags and are exempted."*
- A pre-commit hook (`no-sha-pins-for-internal-actions` in `.pre-commit-config.yaml`) blocks future SHA pins on `projectbluefin/` actions at commit time

**Temporary workaround SHAs** (e.g. pinned to a pre-merge fix): remove as soon as the fix lands in the target branch's `main`. If you're unsure, check whether the referenced PR has merged — if yes, switch back to the managed tag immediately.

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

**`lts` branch is always "ahead" of `main`.**
`execute-release.yml` fast-forwards `lts` after a release. If `lts` has diverged, the fast-forward fails — see `release.md` for the force-update command.

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
        - 'image-versions.yaml'
        - 'Justfile'
      nvidia:
        - 'Containerfile'
```

Using the default (bluefin paths: `build_files/**`, `image-versions.yml`) would silently skip builds when real image changes land.

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

**Rechunk is skipped for `stream_name == testing`** (on-push builds to `main`). Only production builds (`stream_name: lts`) rechunk.

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
| `bluefin-gdx` | https://github.com/orgs/projectbluefin/packages/container/bluefin-gdx/settings |

On each settings page:
1. **Connected repository** → set to `projectbluefin/bluefin-lts`
2. **Manage Actions access** → "Add repository" → `projectbluefin/bluefin-lts` → **Write**

Once done, `github.token` from any `bluefin-lts` workflow has full package read/write — no PAT needed.

> **Note:** `bluefin-lts` is currently (incorrectly) linked to `projectbluefin/bluefin` and `bluefin-gdx`
> has no linked repo. Until an org admin fixes this, GHCR pushes from `bluefin-lts` workflows will fail
> with `DENIED`. The fix is the two-step UI action above — not a new secret.

## SBOM rules

- Generate/attest SBOMs **only** on `refs/heads/lts` **and** when `inputs.publish` is true.
- All SBOM steps must keep `continue-on-error: true`.
- Failed SBOM attestation must never block image publishing.
- LTS uses SPDX JSON artifacts on the amd64 manifest digest; signing uses keyless cosign (Sigstore OIDC).

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
| SBOM steps | `github.ref == 'refs/heads/lts' && inputs.publish` + `continue-on-error: true` |
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

**Design:** The always-open `auto/promote-testing-to-main` PR is the release gate. Merge it (requires 2 maintainers) to cut a release. Gate checks run automatically after each promotion update.

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

**After a testsuite fix merges** the workaround is already live — `run-testsuite.yml` uses `@main`, which always tracks the head of the testsuite's default branch. No SHA bump needed. Remove any temporary KERNEL_ARGS mask in the testsuite if the fix makes it obsolete, but no action is required in bluefin-lts itself.

**Never SHA-pin `projectbluefin/testsuite`.** Even as a temporary workaround, a SHA pin in `run-testsuite.yml` will cause `Lint & syntax` to fail permanently (the `no-sha-pins-for-internal-actions` hook catches it), blocking the entire Renovate automerge pipeline. If you need to pin to a specific testsuite commit while waiting for a fix to merge, hold off on merging PRs that trigger E2E instead.

If stale SHA pins from a previous workaround are present on Renovate branches, update those branches with:
```bash
gh pr update-branch <PR_NUMBER> --repo projectbluefin/bluefin-lts
```
This rebases the branch onto main (which has the `@main` fix) and re-triggers CI.

---

## Trivy scan FATAL — CentOS 10 CPE indices missing

**Symptom:** All three build jobs (`Build Bluefin LTS`, `Build Bluefin LTS HWE`, `Build Bluefin GDX`) fail at the `image (main, …, testing, x86_64)` step with exit code 1 and no obvious container build error. The actual error is Trivy crashing at the very end of the job (after a successful container build):

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
