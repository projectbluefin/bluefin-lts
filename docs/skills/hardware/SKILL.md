---
name: hardware
description: >-
  Change hardware hooks and device integration safely. Use when modifying setup hooks, services, or device-specific image behavior.
---

# Hardware Setup — bluefin-lts

## When to Use

Use when changing setup hooks, hardware services, or device-specific image behavior.

## When NOT to Use

Do not use for generic package, CI, or release changes.

## Common Rationalizations

- “The hook can live locally.” Confirm which layer owns the shared behavior first.

## Red Flags

- Removing a local hook before the containing shared layer is pinned and verified.

## Hook architecture

`projectbluefin/common` ships the hook runner infrastructure in `system_files/shared/`:

- `/usr/bin/ublue-user-setup` — the dispatcher binary
- `/usr/lib/systemd/user/ublue-user-setup.service` — runs on first user login
- `/usr/lib/ublue/setup-services/libsetup.sh` — shared library (`version-script` idempotency guard)

Downstream images drop hook scripts into one of three directories:

| Directory | When it runs | Who calls it |
|---|---|---|
| `usr/share/ublue-os/system-setup.hooks.d/` | System-level, at first boot | `ublue-system-setup` |
| `usr/share/ublue-os/user-setup.hooks.d/` | Per-user, on first login | `ublue-user-setup.service` |
| `usr/share/ublue-os/privileged-setup.hooks.d/` | Elevated, first login | `ublue-user-setup` (polkit) |

**Critical:** `ublue-user-setup.service` is NOT auto-enabled by systemd presets in Containerfile
builds. If it is not explicitly enabled, no user-setup hooks run silently.

```bash
# Verify it is enabled in build_scripts/40-services.sh:
grep 'ublue-user-setup' build_scripts/40-services.sh
```

If absent, add:
```bash
systemctl enable ublue-user-setup.service
```

## Hardware hooks: shipped by common, not by bluefin-lts

**bluefin-lts does not ship any hardware hooks directly.** They are provided by
`projectbluefin/common` and land automatically via the common OCI layer.

The shared layer currently provides the following hooks:

| File in common | Effect |
|---|---|
| `system-setup.hooks.d/10-framework.sh` | Intel keyboard fix (hid_sensor_hub blacklist); Framework 13 AMD suspend + ALSA fixes keyed to BIOS version |
| `user-setup.hooks.d/10-theming.sh` | Framework logo + natural scroll + font scaling; Ampere/Thelio Astra logo |
| `framework-logo-symbolic.svg` | Icon asset referenced by 10-theming.sh |
| `ampere-logo-symbolic.svg` | Icon asset referenced by 10-theming.sh |

### Updating common hooks

If a new hardware quirk needs a hook:
1. File the hook in `projectbluefin/common` (not in bluefin-lts)
2. Bump `image-versions.yaml` `common.digest` in bluefin-lts to the new published common image
3. Verify with `skopeo inspect docker://ghcr.io/projectbluefin/common@sha256:<digest>` that the hook files are present before bumping

### Removing a local hook that moved to common

Use this pattern when a local hook moves to the shared layer:

1. Confirm the hook is present in the published common image — **check the digest date, not the PR date**
2. Bump `image-versions.yaml` to a common digest that postdates the commit adding the hook
3. Remove the local file in the same commit as the bump — they must be atomic
4. Never remove the local file before the common digest is bumped; users who update will silently lose the hardware setup with no error

## Writing a new hardware hook

1. Create the script in `system_files/usr/share/ublue-os/<type>-setup.hooks.d/NN-name.sh`
2. Source `libsetup.sh` and use the `version-script` guard for idempotency:

```bash
#!/usr/bin/env bash
source /usr/lib/ublue/setup-services/libsetup.sh
version-script <name> <scope> <version> || exit 0
set -xeuo pipefail
# ... hardware detection and setup ...
```

3. Use DMI files for hardware detection — no external tools needed:
   - `cat /sys/devices/virtual/dmi/id/chassis_vendor` → `Framework`, `System76`, etc.
   - `cat /sys/devices/virtual/dmi/id/product_name` → `Thelio Astra`, `Laptop (12th Gen Intel Core)`, etc.

4. Verify `ublue-user-setup.service` is enabled in `build_scripts/40-services.sh`.

## CentOS compatibility notes for hardware hooks

- `grubby` is available on CentOS Stream — kernel arg management works the same as Fedora
- `dconf write` is available — icon/setting hooks work without modification
- `glib-compile-schemas` is available — extension schema compilation works
- `brew` is present in bluefin-lts — it ships via a dedicated brew image layer (`BREW_IMAGE_REF`)
  copied in the Containerfile, and `brew-setup.service` is enabled in `build_scripts/40-services.sh`.
  Hooks using brew work the same as in bluefin

## NVIDIA — NVIDIA CDI (rootless Podman GPU passthrough)

The `bluefin-lts-nvidia` variant ships full CDI configuration so `podman run --device nvidia.com/gpu=all` works out of the box without root or privileged containers.

### NVIDIA CDI wiring

**`build_scripts/overrides/nvidia/20-nvidia.sh`**
```bash
# Configure nvidia-container-toolkit for rootless use.
# --in-place patches /etc/nvidia-container-runtime/config.toml directly into the image.
# Required for bootc — cgroup device delegation is not available in unprivileged containers.
nvidia-ctk config --set nvidia-container-cli.no-cgroups --in-place
```

**`system_files_overrides/nvidia/usr/lib/systemd/system-preset/80-nvidia-container-toolkit.preset`**
```
enable nvidia-cdi-refresh.path
enable nvidia-cdi-refresh.service
```

`nvidia-cdi-refresh.path` watches `/lib/modules/*/modules.dep` and `/usr/bin/nvidia-ctk`; on change it triggers `nvidia-cdi-refresh.service` which runs `nvidia-ctk cdi generate` and writes `/var/run/cdi/nvidia.yaml`. This means CDI regenerates automatically on driver or toolkit updates without any user action.

### Why `no-cgroups` is required on bootc

bootc images run in unprivileged OCI containers at build time and on first boot the cgroup v2 device controller delegation path that `nvidia-container-cli` normally uses is not available. Without `no-cgroups`, Podman GPU containers fail with a cgroups permission error at runtime.

### Testing

```bash
podman run --rm \
  --device nvidia.com/gpu=all \
  --security-opt=label=disable \
  nvcr.io/nvidia/cuda:12.4.1-base-ubuntu22.04 \
  nvidia-smi
```

### Reference

Keep this wiring aligned with the shared NVIDIA image-layer implementation. When
that implementation changes, verify the corresponding toolkit configuration,
systemd presets, and runtime test before updating this image.

## NVIDIA — why bluefin-lts does not use upstream `nvidia-install.sh`

`build_scripts/overrides/nvidia/20-nvidia.sh` intentionally does not call the
upstream-blessed `ublue-os/akmods` `nvidia-install.sh` used by bluefin and
Bazzite (tracked in projectbluefin/bluefin-lts#435, parent
projectbluefin/bluefin-lts#223). This was evaluated and rejected for the
CentOS Stream 10 base; re-evaluate only if the blockers below change.

| Layer | Upstream `nvidia-install.sh` (Fedora bluefin/Bazzite) | bluefin-lts `20-nvidia.sh` (CentOS Stream 10) |
|---|---|---|
| Package manager | Requires `dnf5` (`dnf5 config-manager`, `dnf5 copr enable`) | CentOS Stream 10 ships `dnf` 4.20 by default, no `dnf5`/COPR CLI (see `centos-vs-fedora` skill) — script uses `dnf`/`dnf config-manager` only |
| Repository setup | Enables/disables a `.repo` file (`negativo17-fedora-nvidia.repo`) baked into the `ublue-os-nvidia-addons` RPM at akmods-image build time for one Fedora release | Builds a transient `--repofrompath` repo pointed at `negativo17.org/repos/nvidia/fedora-<version>/<arch>/`, substituting the Fedora NVR parsed from the mounted akmods RPM filenames (falls back to `FEDORA_AKMODS_VERSION`) |
| Why the repo differs | The packaged `.repo` file assumes Fedora's `$releasever` resolves to a Fedora release number | CentOS Stream 10's `$releasever` does not resolve to a Fedora release, so the packaged repo would point at the wrong (or a nonexistent) negativo17 path; the transient repo avoids DNF rejecting unavailable source/debug entries on SBSA too |
| akmods/kernel source | `skopeo copy` of `ghcr.io/ublue-os/akmods-nvidia-open:<flavor>-<fedora>-<kernel>` inline in the build script | Same image family, mounted via Containerfile `--mount=type=bind,from=akmods_nvidia_open` using `AKMODS_VERSION=coreos-stable-<fedora>[-<kernel_pin>]` (see `Containerfile`, `Justfile`) |
| kmod-to-kernel matching | Installs the single kmod RPM named for `KERNEL_VERSION`/`NVIDIA_AKMOD_VERSION` from `nvidia-vars` | Filters `/tmp/akmods-nvidia-open-rpms/kmods/*.rpm` for the one whose `Requires` matches the running `kernel-uname-r` — more defensive against multiple staged kmods |
| Driver/kmod version check | Compares `kmod-nvidia` and `nvidia-driver` `%{VERSION}` | Same check, same failure mode |
| CDI / post-install | Enables `ublue-nvctk-cdi.service`, installs the `nvidia-container.pp` SELinux module, forces `i915 amdgpu nvidia` in dracut | Same steps, plus the bootc-specific `nvidia-ctk config --set nvidia-container-cli.no-cgroups --in-place` documented above (upstream Fedora images run privileged enough not to need it) |

### Decision: keep the manual flow

Migrating to `nvidia-install.sh` as-is is blocked by two hard CentOS Stream 10
constraints documented in the `centos-vs-fedora` skill:

1. No `dnf5` by default — the script's `dnf5 config-manager`/`dnf5 copr enable`
   calls would fail outright.
2. No Fedora-resolving `$releasever` — the packaged negativo17 `.repo` file
   would enable against the wrong path, silently breaking signature/repo
   validation instead of failing loudly.

Both constraints are properties of the CentOS Stream 10 base image, not of
this repository's build scripts, so they cannot be fixed locally. The manual
`20-nvidia.sh` flow is the intentional, supported path for this image. Revisit
convergence only if CentOS Stream 10 ships `dnf5` by default, or if
`ublue-os/akmods` adds a CentOS/EL-targeted `nvidia-install.sh` variant.

## Verification

- Confirm the hook or override is owned by the correct image layer.
- Run `just check` and `just lint` after changing build scripts or overrides.
- Test hardware-specific behavior on representative hardware or record why it
  could not be tested.
- Do not claim hardware support from a successful image build alone.
