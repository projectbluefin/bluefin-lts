---
name: bluefin-lts-release
description: >-
  Production release pipeline, branch promotion, registry rollback, and ISO status for
  projectbluefin/bluefin-lts. Use when cutting a release, verifying published images,
  or performing an emergency rollback via skopeo.
metadata:
  type: runbook
  context7-sources:
    - /websites/github_en_actions
---

# Release

## When to Use

- Editing `.github/workflows/promote-testing-to-main.yml`
- Changing weekly promotion cadence
- Debugging why a promotion PR did not auto-merge
- Verifying manual `workflow_dispatch` release cuts
- Emergency rollback or promotion

## When NOT to Use

- Package or image-content changes → `docs/skills/build.md`
- Non-promotion CI failures → `docs/skills/ci-cd.md`
- Hardware-specific image issues → `docs/skills/hardware.md`

## Production release flow

Releases are cut by merging the always-open `auto/promote-testing-to-main` PR.

1. `promote-testing-to-main.yml` runs on push to `testing`, on Tuesday at `04:00 UTC`,
   and on manual dispatch. It calls `reusable-promote-squash.yml@v1` with default inputs
   (`source_branch: testing`, `target_branch: main`). When `testing` and `main` trees differ
   it rebuilds the squash branch and upserts the promotion PR.
2. `pr-release-gate.yml` fires on the promotion PR and verifies cosign signatures + image health.
   Results are posted as a live checklist in the PR body.
3. The promotion PR **auto-merges with squash** once all gate checks pass. Do not click merge
   manually. `execute-release.yml` fires on the resulting push to `main`, re-verifies cosign,
   skopeo-copies `:testing` → `:stable`, and creates a GitHub release with changelog via
   `reusable-release.yml@v1`.

```bash
# Check the promotion PR status
gh pr list --repo projectbluefin/bluefin-lts --head auto/promote-testing-to-main

# Emergency admin merge (bypass gate — only if instructed by maintainer)
gh pr merge <pr-number> --repo projectbluefin/bluefin-lts --squash --admin
```

## Branch protection

`main` branch requires a PR but 0 approvals — gate checks (cosign) are the only gate.
`testing` branch requires a PR but 0 approvals — CODEOWNERS reviews apply for protected paths.
Both branches allow maintainers to bypass via `--admin`.

## Weekly cadence

- Fully automated: **Tuesday 04:00 UTC** — cron fires, promote workflow updates the PR,
  auto-merge triggers, gate checks run, PR merges, execute-release publishes `:stable`
- No human approval required — gate checks (cosign) are the only gate
- `workflow_dispatch` is the supported mid-week release path

## Branch model

- `testing` — active development. All PRs target `testing`. Builds push `:testing` OCI tag.
- `main` — stable. Advances only via squash promotion from `testing`. Push triggers `execute-release.yml`.
- `lts` — archived. No longer part of the active pipeline.

## Image verification — always check digests

Do NOT trust "the fix is in testing" as evidence the fix is published. Verify:

```bash
GHCR_TOKEN=$(gh auth token)
for IMAGE in bluefin-lts bluefin-lts-hwe bluefin-lts-hwe-nvidia; do
  skopeo inspect --creds "castrojo:${GHCR_TOKEN}" docker://ghcr.io/projectbluefin/${IMAGE}:stable \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print('${IMAGE}:stable', d['Digest'][:22], d['Labels'].get('org.opencontainers.image.created','?')[:10])"
done
```

A fix is published when:
1. The `:stable` digest differs from the last known digest
2. The `org.opencontainers.image.created` date is after the fix merged
3. All three variants (bluefin-lts, bluefin-lts-hwe, bluefin-lts-hwe-nvidia) are updated

## Build cascade — rapid commits cancel in-progress builds

Each push to `testing` triggers new builds which cancel in-progress builds via concurrency groups.
Stop committing to `testing` while builds are in progress.

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
  docker://ghcr.io/projectbluefin/IMAGE:stable-YYYYMMDD \
  docker://ghcr.io/projectbluefin/IMAGE:stable
```

Rollback all three variants, then verify digest/created time.

## Emergency promotion for production-bricking bugs

1. Push fix to `testing` — builds trigger automatically.
2. Wait for all 3 builds to complete (~45–90 min). Never promote before builds finish.
3. Verify the new `:testing` image has a fresh initramfs (see Verifying images below).
4. Skopeo-copy `:testing` → `:stable` by digest:

```bash
GHCR_TOKEN=$(gh auth token)
for IMAGE in bluefin-lts bluefin-lts-hwe bluefin-lts-hwe-nvidia; do
  DIGEST=$(skopeo inspect --creds "castrojo:${GHCR_TOKEN}" docker://ghcr.io/projectbluefin/${IMAGE}:testing \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['Digest'])")
  skopeo copy \
    --src-creds "castrojo:${GHCR_TOKEN}" \
    --dest-creds "castrojo:${GHCR_TOKEN}" \
    docker://ghcr.io/projectbluefin/${IMAGE}@${DIGEST} \
    docker://ghcr.io/projectbluefin/${IMAGE}:stable
done
```

Always copy by digest, not tag — prevents races with concurrent pushes.

## Verifying images

### `:testing` — promoted directly by builds

Builds on the `testing` branch publish `:testing` directly (`publish_stream_tag: true` for non-PR
events). PR builds do NOT publish to GHCR.

### `/boot/` is intentionally empty in the OCI image

bootc stores the kernel and initramfs under `/usr/lib/modules/<kver>/`, not `/boot/`. An empty `/boot/` in the container layer is **expected and correct**.

```bash
# Correct way to verify kernel/initramfs health:
podman run --rm ghcr.io/projectbluefin/bluefin-lts:stable bash -c '
  sha256sum /usr/lib/modules/*/initramfs.img
  ls -la /usr/lib/modules/*/vmlinuz
  grep BUILD_ID /etc/os-release
'
```

### OCI label vs BUILD_ID

`org.opencontainers.image.revision` in the OCI manifest may show the `testing` branch SHA.
Use `BUILD_ID` from `/etc/os-release` inside the container as the authoritative commit reference.

### Initramfs must differ from the previous broken build

After a dracut-related fix, verify the initramfs SHA changed:

```bash
# Before promotion: record old SHA
OLD=$(podman run --rm ghcr.io/projectbluefin/bluefin-lts:stable bash -c 'sha256sum /usr/lib/modules/*/initramfs.img' 2>/dev/null | awk '{print $1}')

# After promotion: pull fresh and compare
podman pull ghcr.io/projectbluefin/bluefin-lts:stable
NEW=$(podman run --rm ghcr.io/projectbluefin/bluefin-lts:stable bash -c 'sha256sum /usr/lib/modules/*/initramfs.img' 2>/dev/null | awk '{print $1}')

[ "$OLD" != "$NEW" ] && echo "✅ initramfs changed" || echo "❌ same initramfs — promotion may be a no-op"
```

## ISO status

**LTS ISO is disabled. Do not re-enable.** Anaconda is broken on CentOS Stream base.

## promote-testing-to-main.yml — reusable workflow internals

The caller omits `source_branch` and `target_branch` — the reusable defaults to `testing → main`.

The reusable workflow:
- Checks out the calling repo for git history
- Does a sparse checkout of `projectbluefin/actions` into `.workflow-scripts/`
- Creates PR via `gh pr create` targeting `main`
- Auto-merge fires via `--auto` once gate checks pass

## Red Flags

- `use_merge_queue: true` — `main` uses classic branch protection (0 approvals), not a merge queue; use `--auto` instead
- describing the schedule as Thursday or daily (it is Tuesday)
- adding required approvals to `main` or `testing` branch protection
- referencing `:lts` tag — the stable tag is `:stable`
- referencing the `lts` branch as active — it is archived

## Verification

- [ ] `promote-testing-to-main.yml` schedules Tuesday at `0 4 * * 2`
- [ ] `use_merge_queue: false` (always — enables `--auto` merge on gate pass)
- [ ] push to `testing` trigger present
- [ ] `execute-release.yml` fires on `main` push, copies `:testing` → `:stable`
- [ ] `main` branch protection: `required_approving_review_count: 0`
