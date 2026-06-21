---
name: bluefin-lts-release
description: >-
  Production release pipeline, branch promotion, registry rollback, and ISO status for
  projectbluefin/bluefin-lts. Use when cutting a release, performing an emergency rollback via
  skopeo, managing the lts branch, verifying published images, or checking ISO status.
metadata:
  type: runbook
  context7-sources:
    - /websites/github_en_actions
---

# Release

## When to Use

- Editing `.github/workflows/promote-testing-to-main.yml`
- Changing weekly `main → lts` promotion cadence
- Debugging why a promotion PR updated but did not enqueue
- Verifying manual `workflow_dispatch` stable cuts

## When NOT to Use

- Package or image-content changes → `docs/skills/build.md`
- Non-promotion CI failures → `docs/skills/ci-cd.md`
- Hardware-specific image issues → `docs/skills/hardware.md`

## Core Process

1. Let `workflow_run` events keep the promotion PR fresh after `main` changes.
2. Use the weekly fallback schedule on **Thursday 04:00 UTC** for automatic
   `main → lts` release evaluation.
3. Keep `use_merge_queue` conditional so only `schedule` and
   `workflow_dispatch` enqueue; `workflow_run` should refresh the PR without
   forcing it into the queue.
4. Preserve `source_branch: main` and `target_branch: lts`.
5. Treat `do-not-merge` as a hard stop for auto-merge.

## Production release flow

Releases are cut by merging the always-open `auto/promote-testing-to-main` PR.

1. `promote-testing-to-main.yml` runs on `workflow_run` after `main` moves, on
   Thursday at `04:00 UTC`, and on manual dispatch. It calls
   `reusable-promote-squash.yml` with `source_branch: main` and
   `target_branch: lts`. When `main` and `lts` trees differ it rebuilds the
   squash branch and upserts the promotion PR.
2. The gate job verifies cosign signatures, resolves digests, and checks for a passing post-merge E2E run. Results are posted as a live checklist in the PR body.
3. The promotion PR **auto-merges with squash** once all gate checks pass — `allow_auto_merge` is enabled by `reusable-promote-squash.yml` and the `lts` branch requires 0 approvals. Do not click merge manually. `execute-release.yml` fires on the resulting push to `lts`, re-verifies cosign, skopeo-copies `:testing` → `:lts`, and creates a GitHub release with changelog via `reusable-release.yml@v1`.

```bash
# Check the gate status
gh pr list --repo projectbluefin/bluefin-lts --head auto/promote-testing-to-main

# Force merge — emergency bypass of branch protection (2-approval gate)
gh pr merge <pr-number> --repo projectbluefin/bluefin-lts --squash --admin
```

## Branch protection

`lts` branch requires a PR but 0 approvals — the gate checks (cosign + E2E) are the only gate. `main` requires 2 approvals from `@projectbluefin/maintainers`. `maintainers` team members can bypass with `--admin`.

## Gate checklist — E2E skipped for CI-only commits

When recent commits to `main` are CI-only (no image changes), `Post-Merge E2E — Testing Parity` is skipped, not run. The gate shows ⏳ because it cannot find a passing E2E run. Fix by dispatching manually:

```bash
gh workflow run "Post-Merge E2E — Testing Parity" --repo projectbluefin/bluefin-lts
```

The gate reruns automatically when the promotion workflow next fires
(Thursday fallback schedule, manual dispatch, or next qualifying `workflow_run`).

## Weekly cadence

- Fully automated: **Thursday 04:00 UTC** (midnight ET) — cron fires, promote workflow updates the PR, auto-merge triggers, gate checks run, PR merges, execute-release publishes `:lts` and `:stable`
- No human approval required — gate checks (cosign + E2E) are the only gate
- `workflow_dispatch` is the supported mid-week release path

## Branch model

- `main` — active development. All PRs target `main`. Builds push `:testing` OCI tag.
- `lts` — production. Advances only when `execute-release.yml` fires on a promotion merge.
- `testing` — mirror of `main`. `Sync main → testing` force-syncs after every push to `main`. Used by the promote workflow's trigger chain.

**Never merge `lts → main`.** Flow is one-way: `main → lts`.
**Never push directly to `lts`.** Pushes do not trigger builds.

## lts branch management

`execute-release.yml` fast-forwards `lts` to the promotion commit SHA. If `lts` has diverged, the fast-forward fails. Fix:

```bash
MAIN_SHA=$(gh api repos/projectbluefin/bluefin-lts/git/refs/heads/main --jq '.object.sha')
gh api repos/projectbluefin/bluefin-lts/git/refs/heads/lts \
  --method PATCH --field sha="$MAIN_SHA" --field force=true
```

## Image verification — always check digests

Do NOT trust "the fix is in main" as evidence the fix is published. Verify:

```bash
GHCR_TOKEN=$(gh auth token)
for IMAGE in bluefin-lts bluefin-lts-hwe bluefin-lts-hwe-nvidia; do
  skopeo inspect --creds "castrojo:${GHCR_TOKEN}" docker://ghcr.io/projectbluefin/${IMAGE}:lts \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print('${IMAGE}:lts', d['Digest'][:22], d['Labels'].get('org.opencontainers.image.created','?')[:10])"
done
```

A fix is published when:
1. The `:lts` digest differs from the last known digest
2. The `org.opencontainers.image.created` date is after the fix merged
3. All three variants (bluefin-lts, bluefin-lts-hwe, bluefin-lts-hwe-nvidia) are updated

## Build cascade — rapid commits cancel in-progress builds

Each push to `main` triggers new builds which cancel in-progress builds via concurrency groups. GDX is slowest (60-90 min). Stop committing to `main` while builds are in progress.

```bash
SHA=<commit-sha>
gh run list --repo projectbluefin/bluefin-lts \
  --json workflowName,status,conclusion,headSha \
  --jq "[.[] | select(.headSha | startswith(\"$SHA\")) | select(.workflowName | contains(\"Build\"))]"
```

## Registry queries

```bash
gh auth token | skopeo login ghcr.io -u castrojo --password-stdin
skopeo list-tags docker://ghcr.io/projectbluefin/bluefin-lts
skopeo list-tags docker://ghcr.io/projectbluefin/bluefin-lts-hwe
skopeo list-tags docker://ghcr.io/projectbluefin/bluefin-lts-hwe-nvidia
```

Images publish to:
- `ghcr.io/projectbluefin/bluefin-lts`
- `ghcr.io/projectbluefin/bluefin-lts-hwe`
- `ghcr.io/projectbluefin/bluefin-lts-hwe-nvidia`

## Emergency rollback

```bash
GHCR_TOKEN=$(gh auth token)
skopeo copy \
  --src-no-creds \
  --dest-creds "castrojo:${GHCR_TOKEN}" \
  docker://ghcr.io/projectbluefin/IMAGE:lts-YYYYMMDD \
  docker://ghcr.io/projectbluefin/IMAGE:lts
```

Rollback all three variants, then verify digest/created time.

## Emergency promotion for production-bricking bugs

1. Push fix to `main` — builds trigger automatically.
2. Wait for all 3 builds to complete (~45-90 min). Never promote before builds finish.
3. Verify the new `:testing` image has a fresh initramfs (see Verifying images below).
4. Skopeo-copy `:testing` → `:lts` by digest:

```bash
GHCR_TOKEN=$(gh auth token)
for IMAGE in bluefin-lts bluefin-lts-hwe bluefin-lts-hwe-nvidia; do
  DIGEST=$(skopeo inspect --creds "castrojo:${GHCR_TOKEN}" docker://ghcr.io/projectbluefin/${IMAGE}:testing \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['Digest'])")
  skopeo copy \
    --src-creds "castrojo:${GHCR_TOKEN}" \
    --dest-creds "castrojo:${GHCR_TOKEN}" \
    docker://ghcr.io/projectbluefin/${IMAGE}@${DIGEST} \
    docker://ghcr.io/projectbluefin/${IMAGE}:lts
done
```

Always copy by digest, not tag — prevents races with concurrent pushes.

## Verifying images

### `:stable` is a floating alias for `:lts`

After every release, `execute-release.yml` runs a `tag-stable` job that `skopeo copy`s `:lts` → `:stable`
by digest for all three variants. Use `:stable` when you want the production tag without knowing the
`lts`-branch naming convention.

```bash
# Verify :stable matches :lts
for IMAGE in bluefin-lts bluefin-lts-hwe bluefin-lts-hwe-nvidia; do
  LTS=$(skopeo inspect --no-tags --creds "castrojo:${GHCR_TOKEN}" docker://ghcr.io/projectbluefin/${IMAGE}:lts | jq -er '.Digest')
  STABLE=$(skopeo inspect --no-tags --creds "castrojo:${GHCR_TOKEN}" docker://ghcr.io/projectbluefin/${IMAGE}:stable | jq -er '.Digest')
  [ "$LTS" = "$STABLE" ] && echo "✅ ${IMAGE}: stable == lts" || echo "⚠️  ${IMAGE}: stable != lts"
done
```

`:stable` may lag `:lts` by a few minutes after a release (the `tag-stable` job runs in parallel with
`post-release-variants`). It is never more than one release behind.

### `:testing` is NOT published directly by the build

The build job does **not** push the `:testing` stream tag on push events.
`post-merge-e2e.yml` gates it: runs after `Build Bluefin LTS HWE` completes, runs E2E smoke,
and only promotes `:testing` on pass. If smoke fails, `:testing` is not updated and a GitHub
issue is opened automatically.

PR builds validate that the image builds but do not push to GHCR. A new package name will show
`name unknown` in `skopeo list-tags` until the first post-merge push completes.

### `/boot/` is intentionally empty in the OCI image

bootc stores the kernel and initramfs under `/usr/lib/modules/<kver>/`, not `/boot/`. An empty `/boot/` in the container layer is **expected and correct**. bootc populates the real `/boot` partition from `/usr/lib/modules/` during deployment.

```bash
# Correct way to verify kernel/initramfs health:
podman run --rm ghcr.io/projectbluefin/bluefin-lts:lts bash -c '
  sha256sum /usr/lib/modules/*/initramfs.img
  ls -la /usr/lib/modules/*/vmlinuz
  grep BUILD_ID /etc/os-release
'
```

### OCI label vs BUILD_ID

`org.opencontainers.image.revision` in the OCI manifest may show the `testing` branch SHA rather than the `main` branch commit that built the image (the reusable build workflow in `projectbluefin/actions` uses `github.sha` which resolves to the triggering branch HEAD). Use `BUILD_ID` from `/etc/os-release` inside the container as the authoritative commit reference.

### Initramfs must differ from the previous broken build

After a dracut-related fix, verify the initramfs SHA changed:

```bash
# Before promotion: record old SHA
OLD=$(podman run --rm ghcr.io/projectbluefin/bluefin-lts:lts bash -c 'sha256sum /usr/lib/modules/*/initramfs.img' 2>/dev/null | awk '{print $1}')

# After promotion: pull fresh and compare
podman pull ghcr.io/projectbluefin/bluefin-lts:lts
NEW=$(podman run --rm ghcr.io/projectbluefin/bluefin-lts:lts bash -c 'sha256sum /usr/lib/modules/*/initramfs.img' 2>/dev/null | awk '{print $1}')

[ "$OLD" != "$NEW" ] && echo "✅ initramfs changed" || echo "❌ same initramfs — promotion may be a no-op"
```

## ISO status

**LTS ISO is disabled. Do not re-enable.** Anaconda is broken on CentOS Stream base.

## promote-testing-to-main.yml — reusable workflow internals

The caller passes `source_branch: main` and `target_branch: lts` to `reusable-promote-squash.yml@v1`. **This is critical.** The reusable workflow defaults to `testing → main` — without these inputs, `testing` and `main` trees are always identical and no PR is ever created.

The reusable workflow:
- Checks out the calling repo for git history
- Does a sparse checkout of `projectbluefin/actions` into `.workflow-scripts/` to access `scripts/render_pr_body.py`
- Creates PR via `gh pr create` and extracts the PR number from the returned URL (`--json` flag not available in runner's gh version)
- Assigns review to `@projectbluefin/maintainers` team on create

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "workflow_run should auto-merge too." | No. It should refresh the PR after `main` moves; auto-merge is already set by `--auto` — no extra action needed. |
| "Manual dispatch needs special handling." | It is the supported mid-week release path; `use_merge_queue: false` covers both schedule and dispatch identically. |
| "Thursday timing does not matter." | It intentionally trails bluefin by two days. |

## Red Flags

- `use_merge_queue: true` — lts uses classic branch protection, not a merge queue ruleset; use `--auto` instead
- removing `source_branch: main` or `target_branch: lts`
- describing the schedule as nightly or daily
- adding required approvals back to `lts` branch protection

## Verification

- [ ] `promote-testing-to-main.yml` schedules Thursday at `0 4 * * 4`
- [ ] `use_merge_queue: false` (always — enables `--auto` merge on gate pass)
- [ ] `workflow_run` remains enabled for main-driven PR refreshes
- [ ] `source_branch: main` and `target_branch: lts` remain intact
- [ ] `lts` branch protection: `required_approving_review_count: 0`
