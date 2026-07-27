# Agent instructions

## Purpose

This repository builds and publishes a long-term-support bootable image. Source
files and workflows are the authoritative definition of behavior. This file
provides navigation, safety boundaries, and required validation for coding
agents.

## Navigation

1. Read this file.
2. Read [`docs/skills/INDEX.md`](docs/skills/INDEX.md).
3. Load only the skill matching the task.
4. Inspect the source file or workflow that owns the behavior.
5. Update the owning documentation when a durable rule changes.

Do not load every skill for a narrow task.

## Repository map

- `Containerfile`: image build definition.
- `build_scripts/`: package, service, extension, and metadata steps.
- `system_files/`: files installed into the image.
- `system_files_overrides/`: variant- and architecture-specific files.
- `.github/workflows/`: CI, testing, promotion, and release automation.
- `docs/`: contributor, architecture, quality, release, and agent skills.

## Common commands

```bash
just check
just lint
just unit-tests
pre-commit run --all-files
actionlint .github/workflows/*.yml
```

Before requesting review, run:

```bash
just check && pre-commit run --all-files
```

Use the build and testing skills before starting a long image or VM test.

## Required boundaries

Stop and request human direction before:

- changing architecture or user-visible behavior;
- changing authentication, signing, secrets, supply-chain inputs, or release gates;
- making a breaking change for downstream consumers;
- bypassing validation, signature checks, or branch protection.

Do not cancel long-running image builds. Use an appropriate timeout.

Do not modify installed upstream/vendor documentation unless the task explicitly
concerns that vendor content.

## Branch and release safety

Follow the branch and promotion behavior defined by the current workflows. Do
not infer release behavior from tags alone. Verify published artifacts by
immutable digest and signature.

## Documentation rules

- Keep durable rules in one canonical document.
- Keep skills actionable and under their size budget.
- Update the relevant skill in the same change as the behavior it documents.
- Do not add session logs, dated status, issue histories, or duplicate policy.
- Use standard Markdown and repository-relative links.

## Completion evidence

Before handoff, report:

- checks and tests run;
- workflow or artifact evidence where applicable;
- skipped checks and why;
- remaining risks or unverified live behavior.

## Commit convention

Use Conventional Commits and include the repository-required AI attribution
trailer.
