# Contributing to Bluefin LTS

Thanks for helping out.

Bluefin LTS is the long-term-support Bluefin variant built on a **CentOS Stream 10** base. Because it targets a longer support window, prefer conservative, low-risk changes and document behavior clearly.

General contributor guidance lives at [docs.projectbluefin.io/contributing](https://docs.projectbluefin.io/contributing).

## What is Bluefin LTS?

Bluefin LTS uses `bootc-image-builder` (BIB) on CentOS Stream 10 — **not** `podman build` on Fedora like mainline Bluefin. This gives a longer support lifecycle at the cost of a more conservative package set.

- **Base:** CentOS Stream 10 (`centos_version` in `Justfile`)
- **Build tool:** `bootc-image-builder` (BIB)
- **Variants:** `bluefin-lts`, `bluefin-lts-nvidia`
- **Published tag:** `:stable` (with `:testing` for the pre-release stream)

When in doubt about whether a change belongs here or in [`projectbluefin/common`](https://github.com/projectbluefin/common), prefer `common` for shared system files.

## Pull requests

- Open PRs against the `testing` branch
- Run `just check && just lint` before opening a PR
- PR CI on `testing` runs lint/syntax validation; the E2E smoke test is informational only (see [issue #34](https://github.com/projectbluefin/bluefin-lts/issues/34))

## Prerequisites

- `just` — install with `brew install just` or your OS package manager
- `pre-commit` — install with `pip install pre-commit`, then run `pre-commit install`
- `podman` / `buildah` — required for local image builds
- ~22 GB free disk space for a full CentOS-based image build

`just check` validates Justfile syntax and related script checks. `pre-commit run --all-files` runs linting and formatting hooks.

## Local build

```bash
git clone https://github.com/projectbluefin/bluefin-lts
cd bluefin-lts
just check          # Validate syntax — no containers needed
just lint           # Run pre-commit hooks
just build          # Full image build (~22 GB, slow on first run)
```

The build uses `bootc-image-builder` (BIB) under the hood. See `Justfile` for the `bib_image` and `centos_version` variables that control the base.

## Common pitfalls

- Changes to shared system files (udev rules, sysctl, etc.) belong in [`projectbluefin/common`](https://github.com/projectbluefin/common), not here
- This is **not** the Fedora-based Bluefin; Fedora-specific package names or COPR repos may not exist on CentOS Stream 10
- "Conservative, low-risk changes" means: prefer backporting fixes over new upstream versions unless there is a clear security or stability reason

This repository builds the LTS images themselves. If your change belongs in the shared layer, you may be looking for [projectbluefin/common](https://github.com/projectbluefin/common) instead.
