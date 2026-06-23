---
name: hardware
description: >-
  OEM hardware detection, first-boot setup hooks, and device-specific configuration in
  bluefin-lts. Covers the ublue-user-setup hook architecture, Framework laptop support,
  Ampere/Thelio Astra support, and the gap vs bluefin.
metadata:
  type: runbook
---

# Hardware Setup — bluefin-lts

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

Common ships (since commit `7e97675`, 2026-06-13, closes #651 #652 #653):

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

This has happened once (PR #208). The pattern to follow:

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

## GDX — NVIDIA CDI (rootless Podman GPU passthrough)

The `bluefin-gdx` variant ships full CDI configuration so `podman run --device nvidia.com/gpu=all` works out of the box without root or privileged containers.

### What's wired (as of 2026-06)

**`build_scripts/overrides/gdx/20-nvidia.sh`**
```bash
# Configure nvidia-container-toolkit for rootless use.
# --in-place patches /etc/nvidia-container-runtime/config.toml directly into the image.
# Required for bootc — cgroup device delegation is not available in unprivileged containers.
nvidia-ctk config --set nvidia-container-cli.no-cgroups --in-place
```

**`system_files_overrides/gdx/usr/lib/systemd/system-preset/80-nvidia-container-toolkit.preset`**
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

Mirrors `projectbluefin/dakota` elements/bluefin-nvidia/nvidia-container-toolkit-preset.bst. When dakota changes its CDI wiring, apply the same change here.
