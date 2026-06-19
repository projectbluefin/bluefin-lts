---
name: agentic-model
description: >-
  Cross-repo agent rules for the projectbluefin factory. Hard rules, branch targets, PR
  comment policy, and session-start checklist. Every agent working in any factory repo must
  read this alongside the per-repo AGENTS.md.
metadata:
  type: reference
---

# Agentic Operating Model — projectbluefin

Cross-repo agent rules. Every agent working in any factory repo MUST read this.
Per-repo specifics live in that repo's `AGENTS.md` — start there, then load this.

## Hard rules

- **AGENTS.md is the per-repo contract.** Read it before touching anything.
- **No castrojo fork.** Push branches directly to `projectbluefin/*` repos.
- **Squash only.** All factory repos use squash merge. Never merge-commit or rebase-merge.
- **Max 4 open PRs per agent at once.** No WIP PRs.
- **One PR per feature.** Never batch unrelated changes into a single PR. Each logical fix gets its own branch and PR — reviewers must be able to revert independently.
- **`just check` before every commit** in repos that have a Justfile.
- **`pre-commit run --all-files` before every commit** in repos with `.pre-commit-config.yaml`.
- **Never push directly to a protected branch.** PRs require `lgtm` from a human.
- **Doc-only exception:** `docs/` edits and `AGENTS.md` changes may be pushed directly to `main` — no PR required. Confirm every staged change is docs-only first:
  ```bash
  git diff --cached --name-only  # must show only docs/* or AGENTS.md
  ```
- **CI gates protect the OCI image artifact.** A check earns `exit 1` only if failure means a broken or wrong image ships. Process conventions (attribution, skill files, doc formatting) are self-enforced by agents and must never appear as CI gates.
- **Attribution on every AI-authored commit (convention, not a CI gate):**
  ```
  Assisted-by: <Model> via <Tool>
  ```
- **🚫 ABSOLUTE PROHIBITION — ublue-os org.** Never create issues, PRs, comments, forks, API writes, or any programmatic action targeting any `ublue-os/*` repository. If a task requires touching upstream → stop and tell the human to report it manually.

## Smallest-change principle

Change only what is necessary to accomplish the stated goal. Do not refactor, rename, or reorganize code adjacent to your change. Every unrequested change is a blast-radius expansion.

## Branch targets

| Repo | PR target | Notes |
|---|---|---|
| `common` | `main` | No testing branch — direct to main |
| `bluefin` | `testing` | Never `main` |
| `bluefin-lts` | `main` | `main→lts` is the promotion path |
| `dakota` | `main` | `testing` is a Renovate staging branch only |
| `knuckle` | `main` | No testing branch |
| `actions` | `main` | Shared actions — no testing branch |
| `bonedigger` | `main` | Factory infrastructure |

**Branch creation rule:** Always cut feature branches from the PR target, not from whatever is currently checked out.

```bash
git fetch origin main
git checkout -b feat/my-change origin/main
# Verify: must show ONLY your commits
git log feat/my-change ^origin/main --oneline
```

## Sensitive paths

Changes to these paths require maintainer review (enforced via CODEOWNERS):

| Repo | Sensitive paths |
|---|---|
| `bluefin-lts` | `.github/workflows/`, `Justfile`, `build_scripts/` |
| `common` | `.github/workflows/`, `system_files/`, `Containerfile` |

## Capturing gaps

Any gap, blocker, or open question you cannot fix this session → file a GitHub issue:

```bash
gh issue create --repo projectbluefin/bluefin-lts \
  --title "ci: <what is broken>" \
  --label "kind/improvement" \
  --body "What: ...\nFix: ...\nAutomatable: yes/no"
```

Use `ai-context` label for agent reliability gaps. Do not append gaps to skill files — skill files are not backlogs.

## PR comment policy

One comment per PR event, max. Combine all findings. Never post a follow-up — edit the existing comment. Never duplicate GitHub UI state (approvals, CI status). @ mentions only when asking someone to do something specific.

## Finding work

```bash
# Queued issues ready to claim
gh issue list --repo projectbluefin/bluefin-lts --label "queue/agent-ready"

# Claim an issue
gh issue comment <number> --repo projectbluefin/bluefin-lts --body "/claim"
```
