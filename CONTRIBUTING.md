# Contributing

This repository builds a long-term-support bootable image. Prefer small,
reviewable changes and document durable behavior in the canonical skill for the
area changed.

## Before editing

1. Read [`AGENTS.md`](AGENTS.md).
2. Load the matching skill from [`docs/skills/INDEX.md`](docs/skills/INDEX.md).
3. Inspect the source files and workflow that own the behavior.
4. Check the current branch and working tree before making changes.

## Local prerequisites

- `just`
- `pre-commit`
- `podman` and `buildah` for local image builds
- approximately 22 GB free disk space for a full build

## Validation

Run the applicable checks during development:

```bash
just check
just lint
just unit-tests
```

Before requesting review, run:

```bash
just check && pre-commit run --all-files
```

Use [`docs/qa.md`](docs/qa.md) and the testing skill to choose VM, container,
or integration validation. Long image builds require an appropriate timeout and
must not be cancelled.

## Change boundaries

- Keep image-specific changes in this repository.
- Put shared system behavior in the component that owns the shared layer.
- Treat workflows, build scripts, package sources, and signing configuration as
  production code.
- Do not bypass security, signing, or release checks.
- Preserve upstream documentation under `system_files/`.

## Documentation

Update documentation in the same change when behavior, commands, workflow paths,
release expectations, or failure modes change. Add only timeless, actionable
rules to skills. Do not add session logs, issue status, or dated incident notes.

## Pull requests

- Use a Conventional Commit-style title.
- Target the repository's development branch according to its branch protection.
- Include validation evidence and clearly identify skipped checks.
- Request human review for design, security, release, and breaking changes.

See [`SECURITY.md`](SECURITY.md) for vulnerability reporting.
