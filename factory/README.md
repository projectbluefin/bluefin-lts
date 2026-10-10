# GNOME package factory

Builds the GNOME desktop stack (currently seeded from GNOME 50) as RPMs against **CentOS Stream 10**, and
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

- **GNOME 51 itself.** The recipes are the GNOME 50 set. Moving to 51 is a
  version bump across the stack, and `config/upstream-sources.json` is
  regenerated as each one lands. Nothing in the tooling assumes 50.
- **arm64.** The build root and every recipe are amd64.
- **Hermetic builds.** Builds run in the pinned container, which provides the
  correct ABI but is not a build root in the sense `mock` means — no build user,
  no isolation, no reset between packages. See `docs/architecture.md`.
- **No digest for some sources yet.** Any recipe whose lock has no `sha512`
  does not build. `validate.py` names them.
