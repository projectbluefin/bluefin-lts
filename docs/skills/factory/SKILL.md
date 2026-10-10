---
name: factory
description: >-
  The GNOME package factory in factory/. Use when adding, importing, bumping
  or debugging an RPM recipe, changing the build root or source locks, or
  working out which packages a build would produce.
---

# GNOME package factory

`factory/` builds the GNOME stack as RPMs against **CentOS Stream 10** and
publishes it as an OCI repository image the image build copies in with
`COPY --from=`. See [`factory/README.md`](../../../factory/README.md) for the
design and
[`factory/docs/architecture.md`](../../../factory/docs/architecture.md) for the
pipeline.

## When to use

- Adding, importing, bumping or removing a recipe
- Changing `config/upstream-sources.json`, the build root, or a source lock
- Working out what a build would produce, and why
- Debugging a recipe that will not build, or a source that will not verify

## When not to use

- Which packages the image installs → [packages](../packages/SKILL.md)
- Why a package is missing on CentOS → [centos-vs-fedora](../centos-vs-fedora/SKILL.md)
- CI/CD workflow changes → [ci-cd](../ci-cd/SKILL.md)

## The four rules

1. **No build downloads anything.** Every recipe has a lock in
   `config/upstream-sources.json` naming the resolved upstream URL and its
   SHA-512. `source_pipeline.py` verifies before the build and again inside it.
   A recipe with no lock cannot build.

2. **Build order is solved, never declared.** `build_graph.py` derives waves
   from real `BuildRequires` parsed by `rpmspec` in the build root. There are
   no hand-assigned stages anywhere.

3. **Packit is the SRPM gate, not the builder.** Copr has no CentOS Stream 10
   chroot, so Packit-as-a-service would build against the wrong ABI. Binaries
   are built by `factory-build.yml` against the pinned `c10s` root.

4. **A failed package keeps its previous build.** Publication is incremental;
   only the consumer transaction can block the tag.

## Everyday commands

```bash
just factory-check      # the full fast gate; builds nothing
just factory-sources    # resolved source per recipe, and what is unlocked
just factory-plan       # what a build would select, and why
just factory-relock     # re-render config/upstream-sources.json (needs a container engine)
just factory-srpm <pkg> # prove one recipe produces an SRPM
```

Run `just factory-check` before every commit that touches `factory/**` or
`.packit.yaml`. CI runs the same commands.

## Adding a package

1. Seed it, recording provenance:

   ```bash
   python3 factory/tools/seed_from_copr.py \
     --repo https://download.copr.fedorainfracloud.org/results/jreilly1821/c10s-gnome-50 \
     --chroot epel-10-x86_64 --package <name>
   ```

2. `just factory-relock` — resolves `Source0` with `rpmspec` in the build root
   and records the SHA-512.

3. `just factory-packit-config` — re-render `.packit.yaml`.

4. `just factory-check`.

## Traps worth knowing

- **`rpmbuild` must be given the spec path explicitly.** With no argument it
  globs the working directory, finds nothing in the build output directory,
  exits 0, and writes nothing. A green build with no RPMs.
- **CRB is disabled in the c10s image.** `meson`, `ninja-build`,
  `wayland-devel` and `gcc-g++` live only there. Without
  `dnf config-manager --set-enabled crb`, BuildRequires resolution fails on
  "No matching package to install: meson".
- **`rpmvercmp` is not string order.** `50.0` beats `50~rc`, and `1.0.0.10`
  beats `1.0.0.9`. A plain sort seeds the desktop from release candidates.
- **Imported specs carry upstream typos.** `docbook-style-xsl` had a
  malformed `%2F{%version}` that produced a 404 URL. The digest check is what
  surfaced it.
- **Recipes are the GNOME 50 set.** Moving to 51 is a version bump across the
  stack. Nothing in the tooling assumes 50.

## Build and publication verification

- Reuse the rows extracted in CentOS; the host planner must not rerun RPM.
- Pass JSON-encoded chunks to reusable build matrices, including a single package.
- Keep dependency installation and compilation in one container. Resolve RPM
  exit code 11 from generated BuildRequires with a bounded install/retry loop.
- Admit artifacts only from strictly earlier waves; never same-wave siblings.
- Replace seed RPMs by the successful binaries' full source name, splitting
  the NEVR from the right. Failed recipes keep their old binaries and state.
- Resolve the consumer transaction using CentOS/CRB/EPEL and the candidate,
  with DNF download mode; `--assumeno` is not a successful solve signal.
- Sign metadata before copying it into the image, and sign the immutable OCI
  digest before moving a stream tag. Seed extraction uses `/factory`.
- Verify `Factory CentOS smoke` in CI before trusting local fast gates.

These mechanisms are adapted from `projectbluefin/utah-packages`; its
Hummingbird repositories, exclusions, disttags, and bootstrap rules do not
apply to this CentOS buildroot.

## Red Flags

- A recipe with no lock entry, or a lock with no `sha512`
- A hand-assigned build stage
- A `jobs:` section added to `.packit.yaml`
- The build root referenced by tag rather than digest
