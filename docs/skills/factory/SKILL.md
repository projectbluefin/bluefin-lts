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

- **RPM source URL fragments rename the local archive.** `#/name.tar.gz`
  must match the lock filename; it does not select an archive subdirectory.
- **The spec filename can differ from its recipe name.** Discover the single
  `*.spec`, as inventory does; gobject-introspection uses a bootstrap filename.
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
- **GNOME 51 changes API and dependencies.** Keep Mutter's API version,
  Wayland minima, and source locks aligned with upstream meson.build. Remove
  backports already present upstream and rebase remaining patches. Glycin’s
  jpegxl-sys binding also sets a minimum for the private JPEG XL bundle; match
  that minimum instead of bypassing pkg-config checks. Match all
  upstream version minima in BuildRequires, including Pango’s HarfBuzz minimum,
  so the graph selects a factory prerequisite when CentOS is too old. Malcontent
  supplies Initial Setup’s enabled parental controls; lock all of its bundled
  subprojects and expose new pkgconfig capabilities before planning. Manual
  Meson setup calls must use `--wrap-mode=nodownload`; missing dependencies
  must fail instead of fetching an unlocked fallback.

## Build and publication verification

- Reuse the rows extracted in CentOS; the host planner must not rerun RPM.
  Map capabilities through binary subpackage names, explicit Provides, and
  CentOS repository metadata; `pkgconfig(glib-2.0)` is one capability. Add
  explicit versioned Provides to devel subpackages for capabilities absent
  from CentOS metadata, including GTK variants; otherwise missing libraries
  cannot participate in the graph before their first build.
  DNF Python callers must load config and variable files before repos;
  otherwise CentOS metalinks retain the literal `$stream` and return 404.
- Pass JSON-encoded chunks to reusable build matrices, including a single package.
- Keep dependency installation and compilation in one container. Resolve RPM
  exit code 11 from generated BuildRequires with a bounded install/retry loop.
- Retry DNF once with refreshed metadata for mirror/Curl errors only. Missing
  dependencies and signature failures remain fatal.
- Admit artifacts only from strictly earlier waves; never same-wave siblings.
- Replace seed RPMs by the successful binaries' full source name, splitting
  the NEVR from the right. Failed recipes keep their old binaries and state.
- Resolve the consumer transaction using CentOS/CRB/EPEL and the candidate,
  with DNF download mode; `--assumeno` is not a successful solve signal. The
  stack workflow must also install the resolved RPMs without network repos,
  assert the installed core versions are 51, and run `gnome-shell --version`.
  A source version or dependency solve alone does not verify the installed stack.
- Sign metadata before copying it into the image, and sign the immutable OCI
  digest before moving a stream tag. Seed extraction uses `/factory`.
- Verify `Factory CentOS smoke` in CI before trusting local fast gates.

These mechanisms are adapted from `projectbluefin/utah-packages`; its
Hummingbird repositories, exclusions, and disttags do not apply to CentOS.
Bootstrap edges require exact CentOS RPM version witnesses; declared Utah
stages cannot substitute for a successful dependency transaction.

## Red Flags

- A recipe with no lock entry, or a lock with no `sha512`
- A hand-assigned build stage
- A `jobs:` section added to `.packit.yaml`
- The build root referenced by tag rather than digest

## Full-stack verification

Run `factory-stack.yml` on the candidate branch to build the GNOME 51 targets and unmet prerequisites
without a fixed wave-depth limit. Inspect `factory-stack-evidence` for every
package status and bootstrap witness; a partial RPM artifact is not a successful
stack. Generated cargo bundles come from the upstream Cargo.lock, verify each
crate, and carry their own SHA-512 lock. An explicit relative `lockfile` may
select a nested Cargo.lock from the verified archive. Orca 51 uses this for
MathCAT and builds a native RPM with a tested Python extension; preserve its
speech and braille support. Capture `%{cargo_license}` inside a shell group
with redirection after the closing brace, then require a nonempty summary.
A bare parametric macro can consume shell redirection as a macro argument.
Do not run cargo downloads in rpmbuild.

Umockdev builds use the narrow `packages/umockdev/umockdev-seccomp.json` profile to allow
`open_tree` while preserving the default syscall restrictions and capabilities.
Its SELinux tests detect active SELinux, rather than the existence of the
`selinuxenabled` program; keep the full test suite enabled.
