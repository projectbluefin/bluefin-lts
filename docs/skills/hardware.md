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

## Current state of hardware hooks in bluefin-lts

**bluefin-lts ships zero hardware hooks.** Framework laptop users and Ampere/Thelio Astra users
on LTS silently miss all hardware-specific first-boot setup.

The fix is tracked in the centralization epic: **projectbluefin/common#651**

Once that epic lands, common's OCI layer will ship:
- `user-setup.hooks.d/10-theming.sh` — Framework/Ampere icon, natural scroll, font scaling
- `system-setup.hooks.d/10-framework.sh` — kernel args, BIOS detection, Framework 13 fixes
- `framework-logo-symbolic.svg` and `ampere-logo-symbolic.svg` icon assets

## What bluefin ships that lts does not (as of 2026-06)

These live in `projectbluefin/bluefin` `system_files/shared/` and are absent from lts:

| File | Effect |
|---|---|
| `user-setup.hooks.d/10-theming.sh` | Sets Framework/Ampere icon in custom-command-menu; Framework natural scroll + font scaling |
| `user-setup.hooks.d/20-framework.sh` | Installs `framework_tool` + Framework wallpapers via brew |
| `system-setup.hooks.d/10-framework.sh` | Kernel args, BIOS version detection, Framework 13 hardware fixes |
| `icons/.../framework-logo-symbolic.svg` | Icon asset for Framework logo in menu |
| `icons/.../ampere-logo-symbolic.svg` | Icon asset for Ampere logo in menu |

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
