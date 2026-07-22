# Quality assurance

## Validation layers

Run the smallest applicable layer first, then expand based on risk.

| Change | Required evidence |
|---|---|
| Markdown or documentation | link and Markdown checks |
| Justfile or workflow syntax | `just check`, `actionlint` |
| Shell/build script | `just check`, `just lint`, `just unit-tests` |
| Package or image assembly | local build or CI build evidence |
| Boot, service, or hardware behavior | VM or integration test evidence |
| Release or signing logic | completed workflow plus digest/signature verification |

## Fast checks

```bash
just check
just lint
just unit-tests
pre-commit run --all-files
actionlint .github/workflows/*.yml
```

Use only commands applicable to the files changed. A documentation-only change
must still pass Markdown, link, and front-matter validation when those checks are
available.

## Test selection

Load [`docs/skills/testing/SKILL.md`](skills/testing/SKILL.md) for the decision
tree between unit, container, VM, and integration testing.

Use [`docs/skills/build/SKILL.md`](skills/build/SKILL.md) for full image builds.
For the local Lima/QEMU helper, see the [VM testing reference](skills/testing/references/vm-testing.md).
Do not cancel a long-running image build; use an appropriate timeout.

## Evidence requirements

Record:

- command or workflow run;
- commit or artifact under test;
- pass/fail result;
- skipped checks and why;
- artifact tag and immutable digest when applicable.

A green syntax check does not prove that an image boots or that a published
artifact is signed correctly.
