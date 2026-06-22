---
name: bluefin-lts-build
description: >-
  Local build, validation, and variant guide for projectbluefin/bluefin-lts. Use when running
  just build, just check, or just lint; understanding the Regular/HWE/GDX variant map; debugging
  build failures; or building QCOW2/raw disk images for VM testing.
metadata:
  type: procedure
---

# Build

## Contents
- [Prereqs](#prereqs)
- [Fast validation](#fast-validation)
- [Core builds](#core-builds)
- [Variant map](#variant-map)
- [VM / disk artifacts](#vm--disk-artifacts)
- [Repo layout](#repo-layout-for-build-work)
- [Debugging checklist](#debugging-checklist)

## Prereqs

| Tool | Check | Install / note |
|---|---|---|
| `just` | `which just` | If missing: `mkdir -p ~/.local/bin && wget -qO- "https://github.com/casey/just/releases/download/1.34.0/just-1.34.0-x86_64-unknown-linux-musl.tar.gz" \| tar --no-same-owner -C ~/.local/bin -xz just && export PATH="$HOME/.local/bin:$PATH"` |
| `podman` | `which podman` | required for image + VM builds |
| `git` | `which git` | required |

## Fast validation

```bash
just check && just lint
```

- Run before every commit.
- `just check` validates Just syntax (<30s).
- `just lint` runs shellcheck (<10s).

## Unit tests

| Command | What it tests | Time |
|---|---|---|
| `just unit-tests` | bats tests for `build_scripts/` | <5s |
| `pytest tests/test_changelogs.py -v` | pytest tests for `.github/changelogs.py` | <1s |

Both run in CI on changes to `build_scripts/**` and `tests/**`. Use them to verify build script
behaviour locally before pushing.

## Core builds

| Goal | Command | Typical time |
|---|---|---|
| Regular | `just build bluefin testing 0 0 0` | 45-90 min |
| Nvidia | `just build bluefin-lts-hwe-nvidia testing 0 1 0` | 45-90 min |
| HWE | `just build bluefin testing 0 0 1` | 45-90 min |

The `gnome_version` parameter defaults to `"50"`. Override only if testing a future GNOME version.

**HWE and GDX kernel tracking:** For HWE and GDX builds, the Fedora CoreOS stable version is resolved dynamically at build time via `skopeo inspect docker://quay.io/fedora/fedora-coreos:stable`. This version is used to select the matching `coreos-stable-<version>` akmods image tag and is passed as `FEDORA_AKMODS_VERSION` (controls negativo17 Fedora repo for NVIDIA drivers). Override with `COREOS_STABLE_VERSION` env var if you need to pin:

```bash
COREOS_STABLE_VERSION=44 just build bluefin-lts-hwe-nvidia testing 0 1 0   # Nvidia, force Fedora 44 akmods
COREOS_STABLE_VERSION=44 just build bluefin testing 0 0 1   # HWE, force Fedora 44 akmods
```

Regular builds continue to use `centos-10` akmods and the `fedora_akmods_version` parameter (default `"43"`) has no effect on HWE/GDX.

**Never cancel builds.** Use 120+ minute timeouts.

| Variant | What changes |
|---|---|
| Regular (`bluefin-lts`) | base LTS image |
| Nvidia (`bluefin-lts-hwe-nvidia`) | Nvidia drivers, CUDA toolkit, AI/GPU tooling; uses CoreOS stable kernel via `ENABLE_NVIDIA=1` |
| HWE (`bluefin-lts-hwe`) | newer hardware enablement via CoreOS stable kernel |

## Nvidia build internals

The Nvidia variant (`bluefin-lts-hwe-nvidia`) is built from the same `Containerfile` as the other variants
with `ENABLE_NVIDIA=1` passed as a build arg. Key differences from Regular:

- **Kernel:** CoreOS stable (same as HWE) via `coreos-stable-<fedora_ver>` akmods — NOT CentOS 10 akmods
- **Driver source:** negativo17 `fedora-nvidia.repo` (versioned to match the akmods Fedora version)
- **Override directories:** `build_scripts/overrides/nvidia/` + arch-specific `aarch64/nvidia/`, `x86_64/nvidia/`
- **System files:** `system_files_overrides/nvidia/` + arch-specific `aarch64-nvidia/`, `x86_64-nvidia/`
- **Kernel args:** `kargs.d/00-nvidia.toml` written inline in `20-nvidia.sh` (blacklists nouveau, enables nvidia-drm.modeset)
- **CDI:** `nvidia-container-toolkit` configured for rootless Podman access; `ublue-nvctk-cdi.service` enabled via preset
- **FLAVOR label:** `nvidia`; `IMAGE_NAME`: `bluefin-lts-hwe-nvidia`

**When renaming internal build flags or override directories**, always search ALL build scripts including
arch-specific subdirectories (`build_scripts/overrides/aarch64/`, `build_scripts/overrides/x86_64/`) and
scripts like `kernel-swap.sh` that consume the flag. The rename of `ENABLE_GDX` → `ENABLE_NVIDIA`
revealed that `kernel-swap.sh` had been silently dead (checking `ENABLE_GDX` which Containerfile
never passed) — caught by `grep -rn ENABLE_GDX build_scripts/`.

**dracut cross-device (`Invalid cross-device link / os error 18 / EXDEV`) — known recurring failure:**

`/boot` and `/var/tmp` are separate tmpfs mounts in a container `RUN` layer. Any `dnf install` of kernel
packages triggers rpm-ostree's POSTTRANS scriptlet, which calls dracut. Without intervention dracut stages
in `/var/tmp` and tries `rename(2)` to `/boot` → EXDEV.

`DRACUT_TMPDIR` env var **no longer works** in centos-bootc ≥ 6.12.0-233 — the rpm-ostree hook was updated
and no longer reads it. Use the conf.d approach instead:

```bash
# In kernel-swap.sh, BEFORE the first dnf install:
mkdir -p /etc/dracut.conf.d
echo 'tmpdir="/boot"' > /etc/dracut.conf.d/01-tmpdir.conf

dnf -y install "${RPM_NAMES[@]}"

# ... HWE akmods dnf install (also triggers dracut — conf.d still needed here) ...

# AFTER ALL dnf installs — remove so it does not ship in the final image:
rm -f /etc/dracut.conf.d/01-tmpdir.conf
```

For **explicit** `dracut` calls (e.g. `build_scripts/overrides/nvidia/20-nvidia.sh`), add `--tmpdir /boot`
directly to the command line — conf.d is not needed for explicit calls:

```bash
/usr/bin/dracut --no-hostonly --kver "$QUALIFIED_KERNEL" --reproducible --tmpdir /boot --zstd ...
```

See PRs #174, #248 for history. The regression recurs whenever centos-bootc is updated and `kernel-uki-virt`
is absent from the base image — check for EXDEV errors in HWE and nvidia build logs whenever a centos-bootc
digest bump lands.

| Command | Purpose | Time |
|---|---|---|
| `just build-qcow2` | QCOW2 disk from existing local image | 45-90 min |
| `just rebuild-qcow2` | Build image then QCOW2 | 90-180 min |
| `just build-raw` | Raw disk image from existing local image | 45-90 min |
| `just rebuild-raw` | Build image then raw disk | 90-180 min |
| `just build-iso` | Installer ISO (delegates to `projectbluefin/iso`); **LTS ISO is disabled for release/promote** | 45-90 min |
| `just run-vm-qcow2` | Boot QCOW2; web console on `http://localhost:8006` | runtime |
| `just run-vm-raw` | Boot raw disk image | runtime |
| `just run-vm-iso` | Boot ISO | runtime |
| `just create-test-vm [name] [tag] [ssh-key]` | Create Lima VM with SSH for debugging | runtime |
| `just run-test-vm [name] [tag]` | Create and start Lima VM immediately | runtime |

Never run VMs in CI; KVM/graphics are required.

## Repo layout for build work

| Path | Use |
|---|---|
| `build_scripts/` | package install + build logic |
| `system_files/` | base system config |
| `system_files_overrides/` | variant / arch overrides |
| `Containerfile` | main image definition |
| `image.toml`, `iso.toml` | BIB configs |

Workflow guardrails key off these exact names. When copying from bluefin, replace `build_files/` with `build_scripts/` and `image-versions.yml` with `image-versions.yaml`.

## Services from common — must be explicitly enabled

Services shipped from `projectbluefin/common` via systemd presets are **not auto-applied** during the Containerfile build. Preset files (e.g. `00-rechunker-group-fix.preset`) are inert at build time — they only take effect when `systemctl preset-all` is called, which never happens in the LTS build.

**Rule:** Every service that common ships and LTS needs must have a matching `systemctl enable <service>` line in `build_scripts/40-services.sh`.

**Known required enables from common:**

| Service | Purpose | Consequence if missing |
|---|---|---|
| `rechunker-group-fix.service` | Syncs groups to gshadow before `systemd-sysusers` for users from legacy-rechunked images | Black screen / system will not boot |

When adding new services from common, always check whether they arrive via a preset and add the explicit enable. Do not assume the preset file is sufficient.

## Debugging checklist

| Symptom | Check |
|---|---|
| build fails early | `just check && just lint` |
| missing command | `which just podman git` |
| package pulls fail | repo/network timeout; retry after failure completes naturally |
| storage errors | run `just clean`, verify free disk |
| permission issues | some build paths require sudo/root; `gen-sbom` runs as root — `sbom_out/` is chowned back to runner after write |
| **build script `Permission denied` (exit 126)** | A script in `build_scripts/` was committed without the execute bit (`100644` instead of `100755`). Fix: `git update-index --chmod=+x build_scripts/path/to/script.sh && git commit`. Verify with `git ls-tree HEAD build_scripts/` — all `.sh` files must show `100755`. |
| NVIDIA driver version mismatch in Nvidia build | Set `COREOS_STABLE_VERSION=NN` to pin; or let it auto-resolve from CoreOS stable |

Recovery loop:

```bash
just clean
just check && just lint
just build bluefin testing
```

## Unit testing build scripts

`tests/unit/` contains bats tests for `build_scripts/`. Run with:

```bash
just unit-tests        # runs bats tests/unit/
bats tests/unit/       # direct
```

CI runs on `pull_request` via `.github/workflows/unit-tests.yml` (triggers on `build_scripts/**` or `tests/**` changes).

### Bats test authoring patterns

**Always use `BATS_TEST_TMPDIR` for sandbox dirs:**

```bash
setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"   # bats-managed, unique per test
    STUB_BIN="${TEST_ROOT}/stub-bin"
    mkdir -p "${STUB_BIN}"
    export TEST_ROOT STUB_BIN PATCHED_SCRIPT
}
```

Never use `${SCRIPT_DIR}/.bats-sandbox/name.${BATS_TEST_NUMBER:-0}.$$` — `$$` behaviour across bats versions is unreliable and causes non-deterministic failures.

**Pass PATH explicitly via `env` for stub isolation:**

When the script under test uses external commands (e.g. `ghcurl`, `jq`, `numfmt`), pass PATH explicitly rather than relying on `export PATH` surviving bats subprocess boundaries:

```bash
run env PATH="${STUB_BIN}:${PATH}" IMAGE_NAME=bluefin ... bash "${PATCHED_SCRIPT}"
```

This is more reliable than `run my_function` where the function internally calls `bash`. The latter can drop exported PATH depending on bats version.

**Use `#!/usr/bin/env bash` in stubs** (not `#!/usr/bin/bash`) for portability across distros where `/usr/bin/bash` may not be a symlink.

**Neutralise `set -euo pipefail` network calls in patched scripts:**

If the script under test has `set -o pipefail` and ends with optional network calls (badge fetching, API calls), add `|| true` to those lines in the patched script to prevent SIGPIPE from bats' output-capture mechanism killing the test:

```bash
# In setup(), after the main sed patching:
sed -i \
    -e '/ghcurl/s/$/ || true/' \
    -e '/bazaar-install-count/s/$/ || true/' \
    "${PATCHED_SCRIPT}"
```

SIGPIPE occurs when bats closes its capture pipe before all pipeline stages finish writing. With `set -o pipefail`, a killed pipeline stage propagates as non-zero exit, and `[ "$status" -eq 0 ]` fails non-deterministically.
