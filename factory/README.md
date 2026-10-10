# GNOME package factory

Builds the GNOME desktop stack (targeting GNOME 51) as RPMs against **CentOS Stream 10**, and
publishes them as an OCI image the image build copies in.

This directory is the package factory. It is not consumed by anything except
the image build's `Containerfile`, and it does not modify the image directly:
it produces a repository, and the image points dnf at it.

## Why this exists

bluefin-lts is built on CentOS Stream 10, which ships GNOME 47. Until recently
the GNOME 50 stack came from a third-party COPR project
(`jreilly1821/c10s-gnome-50`). That works, and it was the right call while the
stack was somebody else's problem to maintain. It is not a durable answer for
a release line: the repository's contents, its rebuild policy, and its
availability are all outside this project's control.

So the stack is built here, from recipes we control, against the same base the
image ships on.

## What is decided, and why

| Decision | Choice | Reasoning |
|---|---|---|
| Location | `factory/` inside this repo | One place, one token, easy end-to-end test. Cost: factory workflows share this repository's permissions. |
| Output | Signed GHCR OCI repository image | The image copies it in with `COPY --from=` pinned by digest. No third-party package service in the path. |
| Build root | `quay.io/centos-bootc/centos-bootc:c10s`, digest-pinned | Byte-identical to what ships. Anything else is a different ABI target. |
| Packit's role | SRPM gate only | See below. |
| Recipe seed | The existing COPR's SRPMs | These already carry the EL10 adaptations. Starting from them means the GNOME 51 work is the version bump, not the port. |
| Architectures | amd64 for v1 | The image publishes amd64 and arm64. arm64 follows once the amd64 set is green. |

### Why Packit is the gate and not the builder

Packit-as-a-service builds through Copr. **Copr has no CentOS Stream 10
chroot.** EL10 packages are built in `epel-10-*` or `alma-kitten+epel-10-*`,
which is a different ABI target from the `c10s` base this image runs on.

So `.packit.yaml` carries **no `jobs:` section** — Packit Service performs no
work on a pull request — and Packit is used for the one thing it is genuinely
good at here: turning a recipe into an SRPM in a few seconds, so a malformed
spec fails before a build root is installed and a compiler runs for ten
minutes.

Binaries are built by `factory-build.yml`, in this repository's own workflow,
against the pinned `c10s` root.

This is a deliberate scope, and it is the same scope
`projectbluefin/utah-packages` operates under today.

### Why build order is computed, not declared

There is no hand-assigned build stage anywhere in this factory. The order
comes from real `BuildRequires`, parsed by `rpmspec` in the build root:

```
prepare ──► extract_buildrequires.py ──► build_graph.py ──► waves
```

Hand-assigned stages rot. A new `BuildRequires` edge is invisible until a build
fails somewhere downstream, and a stage that is no longer needed still
serializes work. The plan is checked against the workflow's static job graph,
so a deeper plan fails loudly rather than dropping the packages that did not
fit.

### Why nothing downloads during a build

`config/upstream-sources.json` holds, for every recipe, the resolved upstream
URL and its SHA-512. `source_pipeline.py` fetches and verifies **before** the
build starts; `source_pipeline.py verify-staged` re-verifies **inside** the
build, so a source swapped between staging and build fails there rather than
producing an RPM from bytes nobody checked.

A recipe with no lock entry cannot build. There is no fallback to whatever the
build root happens to serve.

## Layout

```
factory/
  config/
    buildroot.json            the pinned c10s build root, its repositories, bootstrap
    factory-contract.json     projectbluefin/common, pinned by commit
    upstream-sources.json     generated; URL + SHA-512 per recipe
  packages/<name>/
    <name>.spec               the recipe
    *.patch                   downstream patches
    .factory-upstream.json    provenance: where this recipe came from
  tools/                      importer, validator, graph, gates
  tests/                      unit tests for the tooling
```

## Everyday commands

```bash
# The fast gate. Runs in well under a minute; no RPM is built.
python3 factory/tools/validate.py
python3 factory/tools/render_packit_config.py --check
python3 -m unittest discover -s factory/tests

# What would a build do, and why
python3 factory/tools/source_pipeline.py report
python3 factory/tools/rebuild_plan.py --full | python3 -m json.tool

# Prove a recipe produces an SRPM (needs a container engine)
python3 factory/tools/srpm_gate.py gnome-shell --output /tmp/gnome-shell.src.rpm
```

## Adding a package

1. Seed it from the reference repository, which records provenance:

   ```bash
   python3 factory/tools/seed_from_copr.py \
     --repo https://download.copr.fedorainfracloud.org/results/jreilly1821/c10s-gnome-50 \
     --chroot epel-10-x86_64 --package <name>
   ```

2. Render its source lock. This resolves the spec's `Source0` with `rpmspec`
   in the build root and records the URL's SHA-512:

   ```bash
   python3 factory/tools/render_source_locks.py --write
   ```

3. Re-render the Packit config and pass the gate:

   ```bash
   python3 factory/tools/render_packit_config.py --write
   just factory-check
   ```

## What is not done yet

Stated plainly, because the list is short and each item is real:

- **Complete desktop validation.** GNOME 51 sources are SHA-512 locked;
  `Factory GNOME stack` builds the targeted stack in the pinned CentOS root.
  RPM success does not establish image composition or desktop/boot behavior.
- **arm64.** The build root and every recipe are amd64.
- **Hermetic builds.** Builds run in the pinned container, which provides the
  correct ABI and a fresh root per recipe. They still use a root build user
  and networked dependency resolution rather than `mock` isolation. See
  `docs/architecture.md`.
- **No digest for some sources yet.** Any recipe whose lock has no `sha512`
  does not build. `validate.py` names them.

## GNOME 51 build verification

Dispatch `factory-stack.yml` on the candidate branch. It selects the GNOME 51 targets plus prerequisites whose exact requirements
CentOS/CRB/EPEL cannot satisfy, then computes every wave from RPM dependencies, builds in fresh containers, and retains per-package
logs, RPMs, buildroot provenance, and a JSON status report. It has no publication
or signing permissions. Both CI and publication admit up to sixteen computed waves and fail explicitly
if the graph exceeds that limit. Per-wave artifacts expose failures while later
waves continue. After every selected recipe succeeds, the consumer check
downloads the complete GNOME transaction, installs those RPMs with all network
repositories disabled, asserts core package versions are 51, and checks the
installed shell executable. This establishes installation and version evidence;
a graphical session and boot still require an image/VM test.

Cycles can use a CentOS/CRB/EPEL provider only when the extractor records a
provider for the exact versioned BuildRequires. The planner removes only cyclic
edges and records those witnesses; it leaves the full graph intact for rebuild
selection. DNF must still solve the complete build transaction. Tests are not
disabled to bootstrap a cycle.

Rust vendor bundles are generated before compilation from the verified archive's
Cargo.lock. Every crate is verified against its upstream SHA-256, and normalized
tar metadata makes the bundle reproducible. Its SHA-512 is independently locked
as a generated source, then checked again inside the build container. Git-based
crate sources are refused.

Umockdev builds use the narrow `packages/umockdev/umockdev-seccomp.json` profile to allow
`open_tree` while preserving the default syscall restrictions and capabilities.
Its SELinux tests detect active SELinux, rather than the existence of the
`selinuxenabled` program; keep the full test suite enabled.

GTK 4.24 requires `pkgconfig(libdrm)` on Linux for `drm_fourcc.h`.
Localsearch 3.12 test helpers include `<stdint.h>` explicitly for fixed-width
integer types; functional tests remain enabled.

Malcontent 0.14 requires GLib 2.84 headers for `g_steal_handle_id`. Declare
that exact build minimum so DNF upgrades the installed CentOS GLib headers
instead of accepting the older base version.

The umockdev seccomp profile lives with its recipe and participates in the input
digest, so a profile change selects a rebuild.
