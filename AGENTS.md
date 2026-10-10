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
- `factory/`: GNOME package factory. Builds the desktop stack as RPMs against
  the pinned CentOS Stream 10 base and publishes it as an OCI repository image
  the Containerfile copies in. Start at
  [`factory/README.md`](factory/README.md); task routing is
  [`docs/skills/factory/SKILL.md`](docs/skills/factory/SKILL.md).
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
just factory-check
pre-commit run --all-files
actionlint .github/workflows/*.yml
```

Before requesting review, run:

```bash
just check && pre-commit run --all-files
```

`just factory-check` is additionally required for anything touching `factory/**`
or `.packit.yaml`.

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

## Package factory boundaries

- **A build never downloads a source.** Every recipe carries a SHA-512 lock in
  `factory/config/upstream-sources.json`. Adding a recipe without one, or
  pointing its primary URL at a Fedora lookaside, is a defect.
- **The build root is pinned by digest** in `factory/config/buildroot.yaml`.
  Moving it changes the ABI every published RPM is attributable to, and needs
  a pull request.
- **Packit is the SRPM gate only.** Adding a `jobs:` section to `.packit.yaml`
  hands binary builds to Copr, which has no CentOS Stream 10 chroot and would
  build against the wrong ABI.
- **`.packit.yaml` is generated.** Edit `config/upstream-sources.json` and run
  `just factory-packit-config`; a hand edit fails `just factory-check` rather
  than diverging silently.

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

## Shared factory contract

Follow the canonical factory workflow in
[`projectbluefin/common`](https://github.com/projectbluefin/common/tree/main/docs).
Local ownership and safety boundaries in this file take precedence when they differ.

## Completion evidence

Before handoff, report:

- checks and tests run;
- workflow or artifact evidence where applicable;
- skipped checks and why;
- remaining risks or unverified live behavior.

## Commit convention

Use Conventional Commits and include the factory AI attribution trailers:

```text
Assisted-by: <model>
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```
