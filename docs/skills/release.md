---
name: bluefin-lts-release
description: >-
  Production release pipeline, branch promotion, registry rollback, and ISO status for
  projectbluefin/bluefin-lts. Use when cutting a release, performing an emergency rollback via
  skopeo, managing the lts branch, verifying published images, or checking ISO status.
metadata:
  type: runbook
---

# Release

## Production release flow

Releases are cut by merging the always-open `auto/promote-testing-to-main` PR.

1. `promote-testing-to-main.yml` runs on every push to `main` (via `Sync main → testing` completion) and on a nightly cron. It calls `reusable-promote-squash.yml@v1` with `source_branch=main, target_branch=lts`. When `main` and `lts` trees differ it rebuilds the squash branch and upserts the promotion PR.
2. The gate job verifies cosign signatures, resolves digests, and checks for a passing post-merge E2E run. Results are posted as a live checklist in the PR body.
3. **2 approvals from `@projectbluefin/maintainers`** are required — branch protection on `lts` enforces this.
4. Merge with a regular merge commit. `execute-release.yml` fires on merge, re-verifies cosign, skopeo-copies `:testing` → `:lts`, fast-forwards the `lts` branch, creates a GitHub release with changelog via `reusable-release.yml@v1`.

```bash
# Check the gate status
gh pr list --repo projectbluefin/bluefin-lts --head auto/promote-testing-to-main

# Merge when gate is green (requires 2 maintainer approvals)
gh pr merge <pr-number> --repo projectbluefin/bluefin-lts --merge

# Force merge — emergency bypass of branch protection
gh pr merge <pr-number> --repo projectbluefin/bluefin-lts --merge --admin
```

## Branch protection

`lts` branch requires 2 approvals from `@projectbluefin/maintainers`. `main` has the same rule. Both are enforced via GitHub branch protection (set 2026-06-12). `maintainers` team members can bypass with `--admin`.

## Gate checklist — E2E skipped for CI-only commits

When recent commits to `main` are CI-only (no image changes), `Post-Merge E2E — Testing Parity` is skipped, not run. The gate shows ⏳ because it cannot find a passing E2E run. Fix by dispatching manually:

```bash
gh workflow run "Post-Merge E2E — Testing Parity" --repo projectbluefin/bluefin-lts
```

The gate reruns automatically when the promotion workflow next fires (nightly cron or next push to main).

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
for IMAGE in bluefin-lts bluefin-lts-hwe bluefin-gdx; do
  skopeo inspect --creds "castrojo:${GHCR_TOKEN}" docker://ghcr.io/projectbluefin/${IMAGE}:lts \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print('${IMAGE}:lts', d['Digest'][:22], d['Labels'].get('org.opencontainers.image.created','?')[:10])"
done
```

A fix is published when:
1. The `:lts` digest differs from the last known digest
2. The `org.opencontainers.image.created` date is after the fix merged
3. All three variants (lts, lts-hwe, gdx) are updated

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
skopeo list-tags docker://ghcr.io/projectbluefin/bluefin-gdx
```

Images publish to:
- `ghcr.io/projectbluefin/bluefin-lts`
- `ghcr.io/projectbluefin/bluefin-lts-hwe`
- `ghcr.io/projectbluefin/bluefin-gdx`

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
3. Skopeo-copy `:testing` → `:lts` by digest:

```bash
GHCR_TOKEN=$(gh auth token)
for IMAGE in bluefin-lts bluefin-lts-hwe bluefin-gdx; do
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

## ISO status

**LTS ISO is disabled. Do not re-enable.** Anaconda is broken on CentOS Stream base.

## promote-testing-to-main.yml — reusable workflow internals

The caller passes `source_branch: main` and `target_branch: lts` to `reusable-promote-squash.yml@v1`. **This is critical.** The reusable workflow defaults to `testing → main` — without these inputs, `testing` and `main` trees are always identical and no PR is ever created.

The reusable workflow:
- Checks out the calling repo for git history
- Does a sparse checkout of `projectbluefin/actions` into `.workflow-scripts/` to access `scripts/render_pr_body.py`
- Creates PR via `gh pr create` and extracts the PR number from the returned URL (`--json` flag not available in runner's gh version)
- Assigns review to `@projectbluefin/maintainers` team on create
