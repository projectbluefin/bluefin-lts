---
name: bluefin-lts-release
description: >-
  Production release pipeline, branch promotion, registry rollback, and ISO status for
  projectbluefin/bluefin-lts. Use when cutting a release, debugging promotion automation,
  performing an emergency rollback via skopeo, or verifying published images.
metadata:
  type: runbook
  context7-sources:
    - /websites/github_en_actions
---

# Release

## When to Use

- Editing `.github/workflows/promote-testing-to-main.yml` or `execute-release.yml`
- Debugging why a promotion PR did not auto-merge
- Performing an emergency production rollback
- Verifying published `:stable` images after a release

## When NOT to Use

- Package or image-content changes → `docs/skills/build.md`
- Non-promotion CI failures → `docs/skills/ci-cd.md`
- Hardware-specific image issues → `docs/skills/hardware.md`

## Branch model (factory standard)

```
testing → main → :stable
```

- `testing` — all PRs target this branch. Builds push `:testing` OCI tag directly on every push.
- `main` — production source. Advances only via squash promotion from `testing`. Triggering `execute-release.yml`.
- No `lts` branch in the promotion flow. The `lts` git branch is archived.

**Never push directly to `main`.** All changes via PR to `testing`, then auto-promoted.
**Flow is one-way: `testing → main`.** Never merge `main → testing` manually.

## Production release flow

1. `promote-testing-to-main.yml` fires on push to `testing`, **daily at 04:00 UTC**, and on manual dispatch.
   It calls `reusable-promote-squash.yml@v1` with `source_branch: testing`, `target_branch: main`, `use_merge_queue: true`.
   When trees differ it rebuilds the squash branch and upserts the `auto/promote-testing-to-main` PR.
2. The PR enters the merge queue (ruleset 17070416 on `main` requires squash + merge queue).
   Required check: `Lint & syntax`. No approvals needed.
3. On merge, `execute-release.yml` fires on `push: main`, detects the commit message
   `"^chore: promote testing to main"`, skopeo-copies `:testing → :stable` for all three variants,
   and creates a GitHub release with changelog via `reusable-release.yml@v1`.

```bash
# Check promotion PR status
gh pr list --repo projectbluefin/bluefin-lts --head auto/promote-testing-to-main

# Emergency bypass (CODEOWNERS or merge queue blocking — requires admin)
gh pr merge <pr-number> --repo projectbluefin/bluefin-lts --squash --admin
```

## Branch protection

`main` requires a PR with merge queue entry. Gate check: `Lint & syntax`. 0 approvals required.
`.github/workflows/` is CODEOWNERS-protected — PRs touching workflow files require `--admin` bypass.

## Daily cadence

- Fully automated: **daily 04:00 UTC** — cron fires, promote workflow updates the PR, merge queue processes it, execute-release publishes `:stable`
- No human approval required — `Lint & syntax` is the only gate
- `workflow_dispatch` is the supported manual release path

## Image verification — always check digests

Do NOT trust "the fix is in main" as evidence the fix is published. Verify:

```bash
GHCR_TOKEN=$(gh auth token)
for IMAGE in bluefin-lts bluefin-lts-hwe bluefin-lts-hwe-nvidia; do
  skopeo inspect --no-tags --creds "castrojo:${GHCR_TOKEN}" docker://ghcr.io/projectbluefin/${IMAGE}:stable \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print('${IMAGE}:stable', d['Digest'][:22], d['Labels'].get('org.opencontainers.image.created','?')[:10])"
done
```

A fix is published when:
1. The `:stable` digest differs from the last known digest
2. The `org.opencontainers.image.created` date is after the fix merged
3. All three variants (bluefin-lts, bluefin-lts-hwe, bluefin-lts-hwe-nvidia) are updated

## Build cascade — rapid commits cancel in-progress builds

Each push to `testing` triggers new builds which cancel in-progress builds via concurrency groups. Builds take 60-90 min. Stop committing to `testing` while builds are in progress.

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

1. Push fix to `testing` — builds trigger automatically on push to `testing`.
2. Wait for all 3 builds to complete (~45-90 min). Never promote before builds finish.
3. Verify the new `:testing` image has a fresh initramfs (see Verifying images below).
4. Skopeo-copy `:testing` → `:stable` by digest:

```bash
GHCR_TOKEN=$(gh auth token)
for IMAGE in bluefin-lts bluefin-lts-hwe bluefin-lts-hwe-nvidia; do
  DIGEST=$(skopeo inspect --no-tags --creds "castrojo:${GHCR_TOKEN}" docker://ghcr.io/projectbluefin/${IMAGE}:testing \
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

### `:testing` is published directly by the build

Build workflows push `:testing` on every push to the `testing` branch. No E2E gate.
PR builds validate that the image builds but do not push to GHCR.

### `/boot/` is intentionally empty in the OCI image

bootc stores the kernel and initramfs under `/usr/lib/modules/<kver>/`, not `/boot/`. An empty `/boot/` in the container layer is expected and correct.

```bash
podman run --rm ghcr.io/projectbluefin/bluefin-lts:stable bash -c '
  sha256sum /usr/lib/modules/*/initramfs.img
  ls -la /usr/lib/modules/*/vmlinuz
  grep BUILD_ID /etc/os-release
'
```

### Initramfs must differ from the previous broken build

After a dracut-related fix, verify the initramfs SHA changed:

```bash
OLD=$(podman run --rm ghcr.io/projectbluefin/bluefin-lts:stable bash -c 'sha256sum /usr/lib/modules/*/initramfs.img' 2>/dev/null | awk '{print $1}')
podman pull ghcr.io/projectbluefin/bluefin-lts:stable
NEW=$(podman run --rm ghcr.io/projectbluefin/bluefin-lts:stable bash -c 'sha256sum /usr/lib/modules/*/initramfs.img' 2>/dev/null | awk '{print $1}')
[ "$OLD" != "$NEW" ] && echo "initramfs changed" || echo "same initramfs — promotion may be a no-op"
```

## ISO status

**LTS ISO is disabled. Do not re-enable.** Anaconda is broken on CentOS Stream base.

## Red Flags

- `use_merge_queue: false` — main requires a merge queue (ruleset 17070416); always use `true`
- `source_branch: main` or `target_branch: lts` — model changed; use `testing` → `main`
- adding `run_e2e: true` — no post-merge-e2e gate; builds publish `:testing` directly
- describing the schedule as weekly — cadence is daily at 04:00 UTC (`0 4 * * *`)
- **Claiming completion without live verification:** Never claim a build-fixing task is "fully complete" without noting that the fix is still pending live verification by the active CI pipeline (which takes 45–90 mins). Always clearly differentiate between local code-level/syntax validation and live OCI container build execution.

## Verification

- [ ] `promote-testing-to-main.yml` schedules daily at `0 4 * * *`
- [ ] `use_merge_queue: true`
- [ ] `source_branch: testing` and `target_branch: main`
- [ ] `execute-release.yml` fires on `push: main`, detects `"^chore: promote testing to main"`, publishes `:stable`
- [ ] Build workflows push `:testing` on push to `testing` branch
