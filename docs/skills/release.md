---
name: bluefin-lts-release
description: >-
  Production release pipeline, branch promotion, registry rollback, and ISO status for
  projectbluefin/bluefin-lts. Use when dispatching scheduled-lts-release.yml, performing
  an emergency rollback via skopeo, syncing the castrojo fork, or checking ISO status.
metadata:
  type: runbook
---

# Release

## Production release flow

1. `sync-main-to-lts.yml` auto-promotes `main → lts` on every push via regular merge — no manual PR needed.
2. `push` to `lts` validates only; it does **not** publish images.
3. Dispatch manually to publish:
   ```bash
   gh workflow run scheduled-lts-release.yml --repo projectbluefin/bluefin-lts
   ```
4. `promote` skopeo-copies `:testing` → `:lts` by digest after cosign verify passes. The upgrade-test is **non-blocking** (known false positive on `ghcr.io/ublue-os/` prefix; tracked in testsuite#412 / issue #102).
5. `generate-release` fires after `update-lts-branch` succeeds.

## Promotion / branch safety

- `main→lts` is automated via `sync-main-to-lts.yml` (regular merge, direct git push).
- Never squash-merge `main→lts` directly — the sync workflow does regular merge intentionally.
- Never merge `lts→main`.
- `main` uses a merge queue with **squash** method. Required check: `Lint & syntax`. Linear history enforced.
- `gh pr merge --auto` enqueues — do not promise immediate merge.

## Fork sync pattern (`castrojo` fork)

```bash
git fetch projectbluefin
git rebase projectbluefin/main
git push origin <branch> --force-with-lease

# after merge to projectbluefin
git checkout main
git reset --hard projectbluefin/main
git push origin main --force-with-lease
```

Do not merge `projectbluefin/main` into the fork; rebase instead.

## Registry queries

```bash
gh auth token | skopeo login ghcr.io -u castrojo --password-stdin
skopeo list-tags docker://ghcr.io/projectbluefin/bluefin-lts
skopeo list-tags docker://ghcr.io/projectbluefin/bluefin-lts-hwe
skopeo list-tags docker://ghcr.io/projectbluefin/bluefin-gdx
```

Images publish to:
- `ghcr.io/projectbluefin/bluefin-lts` (base)
- `ghcr.io/projectbluefin/bluefin-lts-hwe` (HWE kernel)
- `ghcr.io/projectbluefin/bluefin-gdx` (NVIDIA/AI)

## Emergency rollback

Use immutable dated tags as rollback sources.

| Image | Floating tag | Rollback source |
|---|---|---|
| `bluefin-lts` | `lts` | `lts-YYYYMMDD` |
| `bluefin-lts-hwe` | `lts` | `lts-YYYYMMDD` |
| `bluefin-gdx` | `lts` | `lts-YYYYMMDD` |

```bash
GHCR_TOKEN=$(gh auth token)
skopeo copy \
  --src-no-creds \
  --dest-creds "castrojo:${GHCR_TOKEN}" \
  docker://ghcr.io/projectbluefin/IMAGE:lts-YYYYMMDD \
  docker://ghcr.io/projectbluefin/IMAGE:lts

skopeo inspect --no-creds docker://ghcr.io/projectbluefin/IMAGE:lts \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('Digest:', d['Digest']); print('Created:', d['Created'])"
```

Rollback every affected floating tag, then verify digest/created time for each.

## ISO status

**LTS ISO is disabled. Do not re-enable or promote it.**

- Do not enable `build-iso-lts.yml` schedules.
- Do not run `promote-iso.yml` with `variant: lts` or `variant: all`.
- Do not run `build-iso-all.yml` for LTS promotion.
- Existing production ISOs remain safe; new LTS ISO builds must stay blocked because Anaconda is broken on the CentOS Stream LTS base.

## PR-as-gate release model (as of 2026-06-09)

**How releases work now:**

1. `promote-testing-to-main.yml` runs daily/on push to `testing` — creates/updates the always-open `auto/promote-testing-to-main` PR with the current testing→main diff
2. The promote workflow inlines a `gate` job that calls `reusable-release-gate.yml@main` — verifies digests, cosign signatures, e2e; posts sticky comment; labels PR `release/ready` or `release/blocked`
3. Maintainers review the PR on Tuesdays (or as needed) — if checks pass, merge to cut a release
4. `execute-release.yml` fires on PR merge — re-verifies, skopeo-copies `:testing` → `:lts`, fast-forwards `lts` branch, creates GitHub release
5. `release-reminder.yml` (daily cron) posts reminder after 7 days if PR is still open

**To cut a release:**
```bash
# Check the gate status
gh pr view 125 --repo projectbluefin/bluefin-lts

# When ready, merge (requires 2 projectbluefin/maintainers approvals)
gh pr merge 125 --repo projectbluefin/bluefin-lts --merge --admin
```

**Branch protection requirement (human must apply in Settings):**

`main` branch in bluefin-lts, bluefin, and dakota should require 2 approvals from `projectbluefin/maintainers` team before merge. This is a GitHub Settings > Branches configuration that agents cannot set.

Path: Repository Settings → Branches → Branch protection rules → main → Require a pull request before merging → Required number of approvals: 2 → Restrict reviews to specific team: `projectbluefin/maintainers`

Until this is configured, a single maintainer can merge. The workflows enforce the intent via the gate checks, but the 2-reviewer gate is a social contract until the branch protection rule is applied.

**Admin bypass:** `--admin` flag on `gh pr merge` bypasses branch protection including the 2-reviewer requirement. Use only for emergency fixes.
