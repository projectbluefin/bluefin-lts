# Release trust

## Release model

Changes are built and tested on the pre-release branch before automated
promotion publishes stable artifacts. The exact branch and workflow behavior is
defined by the repository workflows and the [`release` skill](skills/release/SKILL.md).

## What users should verify

- The image reference is the expected stable or testing stream.
- The resolved digest is recorded and corresponds to the published artifact.
- The artifact has a valid signature under the repository's configured policy.
- Release notes or status identify the tested source revision.

Tags are mutable pointers; use digests for verification and incident response.

## Rollback principle

Rollback must select a previously verified immutable artifact. Do not repair a
release incident by weakening signature policy or silently repointing a stable
tag. Follow the release skill and record the resulting digest and evidence.

## Maintainer procedures

For promotion, registry inspection, signature checks, emergency promotion, or
rollback, load [`docs/skills/release/SKILL.md`](skills/release/SKILL.md). This
page is intentionally a concise trust overview rather than an operator runbook.
