# Remove the human release gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the extra release-gate path that blocks the promotion PR and make the promotion workflow itself carry the E2E gate so `testing` can advance to `main` and `:stable` on the daily cadence.

**Architecture:** The promotion workflow remains the single automation path from `testing` to `main`. It will run E2E during promotion, use the merge queue, and auto-merge once checks pass. The redundant PR-level release-gate workflow is removed so it no longer adds a second gate or action-required state to the promotion PR.

**Tech Stack:** GitHub Actions, Bash, git, pre-commit

---

## Task 1: Update the promotion workflow to own E2E gating

**Files:**
- Modify: `.github/workflows/promote-testing-to-main.yml`

- [ ] **Step 1: Flip the promotion workflow to run E2E**

In `.github/workflows/promote-testing-to-main.yml`, change the `promote` job input from:

```yaml
run_e2e: false
```

to:

```yaml
run_e2e: true
```

- [ ] **Step 2: Add merge-queue validation mirroring**

Add the `mirror-validate-to-merge-group` job from the bluefin workflow so the merge queue sees a `validate` success signal once the promotion workflow finishes.

- [ ] **Step 3: Verify workflow syntax**

Run:

```bash
cd /var/home/jorge/src/bluefin-lts
pre-commit run --all-files
```

Expected: all relevant hooks pass.

---

## Task 2: Remove the redundant PR release gate workflow

**Files:**
- Delete: `.github/workflows/pr-release-gate.yml`

- [ ] **Step 1: Remove the workflow file**

Delete `.github/workflows/pr-release-gate.yml` so the promotion PR no longer gets a separate PR-gate check in the path.

- [ ] **Step 2: Commit the workflow change**

Run:

```bash
cd /var/home/jorge/src/bluefin-lts
git add .github/workflows/promote-testing-to-main.yml .github/workflows/pr-release-gate.yml
git commit -m "fix(ci): remove release-gate handoff and run e2e in promotion"
```

- [ ] **Step 3: Push to testing**

Run:

```bash
cd /var/home/jorge/src/bluefin-lts
git push origin testing
```

---

## Task 3: Trigger the new promotion/e2e path

**Files:**
- None; existing build and promotion workflows are exercised.

- [ ] **Step 1: Watch the promotion workflow**

After the push, confirm that the new `Promote testing to main` run appears and that it starts the E2E gate rather than the old PR-gate workflow.

- [ ] **Step 2: Confirm the promotion PR updates**

Run:

```bash
gh pr view 402 --repo projectbluefin/bluefin-lts --json number,title,mergeStateStatus,reviewDecision,url
```

Expected: the PR is refreshed with the new commit and moves through the promotion workflow rather than being held by the old gate.
