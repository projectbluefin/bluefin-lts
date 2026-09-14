---
name: testing
description: >-
  Choose and run the appropriate unit, container, VM, or integration test. Use when validating image or build-script changes.
---

# Testing — GitHub Actions

## When to Use

Use when validating build scripts, image content, or configuration files.

## When NOT to Use

Do not use this skill to change CI workflow design or release promotion policy.

## Common Rationalizations

- “A container test proves boot behavior.” Container tests do not establish boot behavior.

## Red Flags

- Testing only a mutable tag, skipping the affected variant, or treating a cached image as fresh evidence.

## GitHub Actions test suites

All automated image checks run in GitHub Actions. `.github/workflows/pr-e2e.yml` composes changed system files onto `bluefin-lts:testing`, then calls `.github/workflows/run-testsuite.yml` for the smoke suite. `run-testsuite.yml` is the repository wrapper for the managed testsuite E2E workflow.

For changes not covered by the PR E2E path, add or extend a GitHub Actions workflow rather than relying on external lab infrastructure. Keep checks scoped to affected paths and use the immutable image produced by the workflow.

For state-changing commands in container coverage, shadow them with test stubs before execution. Do not run `bootc switch` or `systemctl enable` in a container test.

## Verification

- Choose the smallest test layer that exercises the changed behavior.
- Record the image reference, source revision, command or workflow, and result.
- Run a VM test when boot, systemd, hardware, or `bootc switch` behavior is involved.
- Report skipped checks and why; do not treat container success as proof of boot success.
