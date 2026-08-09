---
name: ci-cd
description: >-
  Diagnose and change continuous-integration, promotion, and publication workflows.
  Use when a workflow does not trigger, an artifact is not published, or CI logic changes.
metadata:
  context7-sources:
    - /podman-container-tools/skopeo
---

# CI/CD

## When to use

- A workflow does not trigger or selects the wrong paths.
- A testing artifact is not updated or a stable artifact is not promoted.
- A workflow, reusable workflow input, action reference, or publication step changes.

## When not to use

- Local build commands: [`build`](../build/SKILL.md).
- Artifact verification, rollback, or promotion procedure: [`release`](../release/SKILL.md).
- Test selection: [`testing`](../testing/SKILL.md).

## Procedure

1. Read the affected workflow and its caller/callee relationship before editing.
2. Confirm the triggering event, branch, path filters, permissions, secrets, and
   concurrency behavior.
3. Trace every reusable-workflow input from caller to implementation.
4. Check the artifact name, tag, digest, and registry destination at each stage.
5. For manifest assembly, run `bootc-build/setup-runner@v1` first so the caller provides the required Podman tooling.
6. Verify the published manifest digest is an image index containing every expected
   architecture before signing or triggering post-build verification.
7. Make the smallest change that fixes the event or data-flow defect.
8. Validate syntax and repository policy locally.
9. Inspect the resulting workflow run before declaring success.

## Workflow map

| Concern | Inspect first |
|---|---|
| Regular image build | `.github/workflows/build-regular.yml` |
| NVIDIA image build | `.github/workflows/build-nvidia.yml` |
| NVIDIA ARM build | `.github/workflows/build-nvidia-aarch64.yml` |
| NVIDIA manifest assembly | `.github/workflows/build-nvidia-manifest.yml` |
| Promotion | `.github/workflows/promote-testing-to-main.yml` |
| Stable publication | `.github/workflows/execute-release.yml` |
| End-to-end tests | `.github/workflows/run-testsuite.yml`, `pr-e2e.yml` |
| Syntax and repository checks | `.github/workflows/pr-testsuite.yml`, `unit-tests.yml` |
| Lab PR Check Run | `.github/workflows/lab-check.yml` |
| Dependency updates | `.github/renovate.json5`, Renovate workflows |

The exact workflow files in the repository are authoritative. Update this table
when a workflow is renamed or removed.

## Branch and tag flow

- Pull requests target `testing`.
- Builds on `testing` publish the pre-release testing stream.
- Promotion moves tested content toward `main`.
- Release automation publishes stable artifacts from the promotion result.
- Do not manually treat a testing tag as stable without following the release
  skill and verifying the digest and signature.

## Action references

- Pin third-party actions to full commit SHAs with a version comment.
- Use the repository's managed internal action tags where policy requires them.
- Do not add a SHA pin when the repository's policy explicitly requires a managed
  tag.
- Never weaken workflow permissions to make a failing step pass.

## Multi-architecture publication

The reusable build workflow pushes each architecture separately and returns a
platform-to-digest map; it does not assemble the index. The regular caller runs
a follow-on `create-manifest` job after both architectures complete, then signs
the resulting manifest digest. NVIDIA amd64 (`build-nvidia.yml`) and aarch64
(`build-nvidia-aarch64.yml`) build as fully independent, differently-timed
workflow runs so that an ARM build failure never blocks amd64 publication.
Neither publishes `:testing` directly (`publish_stream_tag: 'false'`); both
publish only immutable architecture-specific aliases. `build-nvidia-manifest.yml`
is triggered by either sibling's `workflow_run` completion, finds the latest
successful run of each per-arch workflow for the same commit via `gh api`,
downloads their digest artifacts cross-run, and only assembles, verifies, and
signs the multi-arch `:testing` index once both architectures are present; if
the sibling isn't done yet it exits cleanly and relies on the sibling's own
completion to retry. `workflow_run` triggers only activate for workflow files
present on the repository's default branch (`main`), so changes to
`build-nvidia-manifest.yml` take effect only after promotion to `main`.
Promotion copies the signed testing artifact to the stable tag with
`skopeo copy --all --format oci`, and `execute-release.yml` refuses to promote
any source that is not already a verified amd64+arm64 image index.

When changing architecture inputs or publication tags, verify all of these:

1. The required amd64 build completes and publishes its verified artifact.
2. When a multi-architecture release is intended, the reusable output contains both `amd64` and `arm64` digests.
3. The manifest job publishes the stream tag only after all required architectures finish.
4. The manifest digest resolves to an index containing both platforms.
5. The manifest digest is signed before promotion can verify it.
6. Post-testing verification checks the same immutable digest that the manifest job published.

## Debugging a missing build

Check in order:

1. The event occurred on the expected branch.
2. The changed path matches the workflow filters.
3. The workflow is not disabled or skipped by an expression.
4. Required permissions and secrets are available.
5. The reusable-workflow reference and inputs are valid.
6. Concurrency has not superseded the run.
7. The publication step wrote the expected tag and digest.

Use the GitHub workflow run, job summary, and logs as evidence. Do not infer
success from a green caller job if the reusable job or publication step failed.

Every open Bluefin LTS PR is discovered by the lab's five-minute PR poller. The
lab runs smoke QA against `bluefin-lts:testing` and sends bounded
`repository_dispatch` lifecycle events to `lab-check.yml`, which must exist on
the default branch. That workflow uses a short-lived MergeRaptor installation
token to update one `testing-lab / bluefin-lts` Check Run for the exact PR head
SHA. Do not duplicate the result in a PR comment or commit status.

## Common Rationalizations

- “The caller is green, so publication succeeded.” Inspect the reusable job and artifact.

## Red flags

- Floating third-party action tags.
- Direct calls to a reusable workflow's internal implementation instead of the
  repository wrapper.
- Workflow documentation naming files that no longer exist.
- An artifact tag checked without its immutable digest.
- Permissions broader than the job requires.
- A release or signing failure hidden with `continue-on-error`.
- Copying a workflow from another image variant without checking path and input
  differences.
- Posting a lab result as a PR comment instead of updating the MergeRaptor Check Run.
- Calling `create-manifest@v1` without first preparing the runner.

## Verification

```bash
actionlint .github/workflows/*.yml
just check
pre-commit run --all-files
```

For behavior changes, inspect the completed run and record the workflow URL,
commit, artifact tag, and digest. For signing or release changes, also follow
[`release`](../release/SKILL.md).

## Sources

- Context7: `/websites/github_en_actions` — `repository_dispatch` payloads and
  the requirement that the workflow exist on the default branch.
