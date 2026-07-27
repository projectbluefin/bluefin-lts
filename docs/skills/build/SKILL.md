---
name: build
description: >-
  Local builds, validation, variants, and VM artifacts for projectbluefin/bluefin-lts.
  Use when running just recipes, understanding the LTS/NVIDIA variant map, or debugging
  a build failure.
---

# Build

## When to use

- Running `just build`, `just check`, or `just lint`
- Building the regular LTS or NVIDIA variant
- Building QCOW2/raw disk images or Lima VMs for testing
- Debugging a build failure

## When not to use

- CI/CD workflow changes → [ci-cd](../ci-cd/SKILL.md)
- Production promotion/rollback → [release](../release/SKILL.md)
- Package choices between CentOS and Fedora → [centos-vs-fedora](../centos-vs-fedora/SKILL.md)

## Prerequisites

- `just`
- `podman`
- `git`
- ~22 GB free disk space for a full image build

## Fast validation

```bash
just check      # validate Justfile syntax and build script checks (<30s)
just lint       # shellcheck over build_scripts/**/*.sh
just unit-tests # bats tests for build_scripts/
```

Run before every commit.

## Core builds

| Goal | Command | Time |
|---|---|---|
| Regular LTS | `just build bluefin-lts lts 0 0` | 45–90 min |
| NVIDIA | `just build bluefin-lts-nvidia lts 0 1` | 45–90 min |

`gnome_version` defaults to `50`; override only when testing a future GNOME version.

LTS uses the Fedora CoreOS 44 akmods stream by default. Override it explicitly when validating another compatible stream:

```bash
COREOS_STABLE_VERSION=44 COREOS_STABLE_KERNEL=7.0.12-201.fc44 \
  just build bluefin-lts-nvidia lts 0 1
```

**Never cancel builds.** Use a 120+ minute timeout.

## Variant map

| Variant | What changes |
|---|---|
| `bluefin-lts` | base image, CoreOS-stable kernel track |
| `bluefin-lts-nvidia` | NVIDIA drivers, CUDA toolkit, rootless Podman CDI configuration |

NVIDIA overrides live in `build_scripts/overrides/nvidia/`, `system_files_overrides/nvidia/`, and arch-specific directories.

## VM / disk artifacts

| Command | Purpose |
|---|---|
| `just build-qcow2` | QCOW2 from existing local image |
| `just rebuild-qcow2` | build image + QCOW2 |
| `just build-raw` | raw disk from existing local image |
| `just rebuild-raw` | build image + raw disk |
| `just build-iso` | installer ISO (delegates to `projectbluefin/iso`; LTS ISO is disabled) |
| `just run-vm-qcow2` | boot a QCOW2 locally |
| `just create-test-vm [name] [tag] [ssh-key]` | Lima VM with SSH injected |

Do not run VMs in CI; they require KVM/graphics.

## Fedora CoreOS kernel and microcode

The akmods containers provide Fedora NVR kernels to the CentOS image. The
CentOS `microcode_ctl` dracut module does not recognize those Fedora kernel
versions and can abort initramfs generation. `kernel-swap.sh` temporarily omits
that incompatible module for Fedora kernels and removes the build-only config
in cleanup.

## Dracut cross-device failure (`EXDEV`)

`/boot` and `/var/tmp` are on separate mounts during `RUN` layers. If `dnf install` triggers dracut and it stages in `/var/tmp`, `rename(2)` to `/boot` fails with `Invalid cross-device link`.

Fix in kernel-swap.sh before any dnf install:

```bash
mkdir -p /etc/dracut.conf.d
echo 'tmpdir="/boot"' > /etc/dracut.conf.d/01-tmpdir.conf
# ... dnf installs ...
rm -f /etc/dracut.conf.d/01-tmpdir.conf
```

For explicit dracut calls, add `--tmpdir /boot` directly.

## Services from common must be explicitly enabled

systemd presets from `projectbluefin/common` are inert at Containerfile build time. Every service LTS needs must have a matching `systemctl enable <service>` in `build_scripts/40-services.sh`. A missing enable can leave the system unbootable.

Known required enables:

| Service | Why |
|---|---|
| `rechunker-group-fix.service` | Prevents boot failure on legacy-rechunked group state |

## Debugging checklist

| Symptom | Check |
|---|---|
| build fails early | `just check && just lint` |
| missing command | `which just podman git` |
| storage errors | `just clean`; verify free disk |
| script `Permission denied` | ensure `.sh` files are committed `100755` (`git update-index --chmod=+x`) |
| NVIDIA driver mismatch | pin `COREOS_STABLE_VERSION=NN` and the matching `COREOS_STABLE_KERNEL=NVR` |
| dracut EXDEV | kernel-swap.sh tmpdir config |

## Unit testing

```bash
just unit-tests
bats tests/unit/
```

Bats test authoring patterns:

- Use `BATS_TEST_TMPDIR` for sandboxes.
- Pass `PATH` explicitly via `env` when stubbing commands.
- Use `#!/usr/bin/env bash` in stubs.
- Neutralize optional network calls at the end of patched scripts with `|| true` to avoid SIGPIPE under `set -o pipefail`.

Verification:

- [ ] `just check` passes
- [ ] `just lint` passes
- [ ] `just unit-tests` passes (if build scripts changed)
- [ ] `.sh` files have execute bit

## Common Rationalizations

- “Syntax passed, so the image is fine.” Build or test the affected artifact.
- “This service is preset.” Verify every required service is explicitly enabled.

## Red Flags

- Cancelled long-running builds, missing execute bits, or unverified image output.

## Verification

Use the checklist above and record the command output before review.
