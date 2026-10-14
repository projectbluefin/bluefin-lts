# Architecture

## Purpose

This repository assembles a bootable OCI image from a base image, pinned image
layers, package definitions, system files, and build scripts.

## Build flow

1. Image metadata selects the base and pinned external layers.
2. The `Containerfile` establishes the image build environment.
3. `build_scripts/` installs packages, builds extensions, enables services, and
   writes image metadata.
4. `system_files/` supplies files copied into the image.
5. `system_files_overrides/` supplies variant- or architecture-specific files.
6. CI builds, tests, signs, and publishes immutable artifacts before promotion.

The source files and workflows are authoritative when this overview differs from
implementation.

## Variants

The repository publishes a regular long-term-support image and an NVIDIA-enabled
variant. Both share the main build path; variant-specific packages and files are
isolated in explicit build arguments and override directories.

## Ownership boundaries

- Shared system behavior belongs in the shared image layer that owns it.
- This repository owns variant-specific build configuration and image assembly.
- Vendored desktop-extension documentation is upstream content, not repository
  policy.
- CI workflows own automation behavior; skills explain how to work with them but
  do not replace workflow definitions.

## Trust boundaries

- Base image and external layers are inputs and must remain pinned or verifiable.
- Package and repository additions require compatibility and supply-chain review.
- Signing and promotion gates must not be bypassed to make a build green.
- Release verification must use immutable digests, not tags alone.

## Telemetry

Uranium ships no installation-count telemetry. The Bluefin LTS `countme`
units and their helper script were dropped in the rebrand: there is no Uranium
endpoint to report to, and the only badge endpoint available reported Bluefin's
install count. `build_scripts/40-services.sh` masks `rpm-ostree-countme` and
any leftover `*-countme.timer` unit so an upgrade cannot leave one enabled.

Adding telemetry back requires an endpoint owned by this image, an opt-out path,
and a privacy review. Do not reintroduce the Bluefin endpoint.

For implementation procedures, load the relevant skill from
[`docs/skills/INDEX.md`](skills/INDEX.md).
