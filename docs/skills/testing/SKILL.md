---
name: testing
description: >-
  Choose GitHub Actions unit, image-build, and end-to-end coverage when validating image or build-script changes.
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

All automated image checks run in GitHub Actions:

| Change | Workflow |
|---|---|
| Shell and build-script behavior | `.github/workflows/unit-tests.yml` |
| Image builds | `.github/workflows/build-regular.yml`, `build-nvidia.yml` |
| PR system-files smoke coverage | `.github/workflows/pr-e2e.yml` |
| Shared end-to-end suite | `.github/workflows/run-testsuite.yml` |

`pr-e2e.yml` composes changed system files onto `bluefin-lts:testing`. Same-repository PRs publish that image to GHCR and invoke the smoke suite through `run-testsuite.yml`. Fork PRs receive no package-write credential, so the workflow currently cannot publish a composed image or invoke that cross-job smoke suite. Do not use `pull_request_target` for PR code; add a least-privilege same-job fork smoke path before treating fork coverage as equivalent.

For changes not covered by these paths, add or extend a GitHub Actions workflow. Keep checks scoped to affected paths and use the image built by the workflow.

For state-changing commands in container coverage, shadow them with test stubs before execution. Do not run `bootc switch` or `systemctl enable` in a container test.

## Verification

- Choose the smallest test layer that exercises the changed behavior.
- Record the image reference, source revision, command or workflow, and result.
- For boot, systemd, hardware, or `bootc switch` behavior, add or run dedicated GitHub Actions coverage; do not treat container success as proof of boot behavior.
