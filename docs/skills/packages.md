---
name: bluefin-lts-packages
version: "1.0"
last_updated: 2026-06-23
tags: [packages, rpm, dnf, copr, epel]
description: >-
  Adding, removing, or updating RPM packages in the bluefin-lts image.
  Use when editing package lists, handling COPR packages, or debugging
  dnf install failures in the build.
metadata:
  type: procedure
---

# Package Management

## When to use

- Adding, removing, or updating RPM packages in the image
- Figuring out which build script owns a package
- Debugging dnf install failures in CI

## Package locations

| Type | Location | Notes |
|---|---|---|
| Main install list | `build_scripts/packages/base.toml` `[install]` | From base/EPEL repos |
| Install-time excludes | `build_scripts/packages/base.toml` `[install_excluded]` | Passed as `-x` flags |
| GNOME 50 package list | `build_scripts/packages/base.toml` `[gnome]` | Minimal GNOME group |
| GNOME install excludes | `build_scripts/packages/base.toml` `[gnome_excluded]` | Passed as `-x` flags |
| Packages removed pre-install | `build_scripts/packages/base.toml` `[remove]` | `dnf remove` before main install |
| GNOME versionlock pins | `build_scripts/packages/base.toml` `[versionlock_gnome]` | Pinned against EL10 downgrades |
| GNOME base setup | `build_scripts/overrides/base/10-packages-image-base.sh` | Group installs + repo setup; not TOML |
| NVIDIA driver install | `build_scripts/overrides/gdx/20-nvidia.sh` | Orchestration only; no TOML |
| dx packages | `build_scripts/overrides/dx/00-packages.sh` | VSCode, Docker, libvirt, cockpit |
| gdx packages | `build_scripts/overrides/gdx/30-packages.sh` | uv, nvtop |

## Adding a package

Edit `build_scripts/packages/base.toml`, add to the correct section, then validate:

```bash
# Verify the manifest parses cleanly
python3 build_scripts/scripts/read-packages build_scripts/packages/base.toml install | grep <package>
just check
```

The `read-packages` helper uses `tomllib` (Python 3.11+ stdlib — no new dependencies).
It is called inside build scripts as:
```bash
readarray -t PKGS < <(python3 /run/context/build_scripts/scripts/read-packages \
    /run/context/build_scripts/packages/base.toml install)
```

## Non-obvious patterns

- **Group installs stay in shell.** `dnf group install "Core"` and similar stay in `10-packages-image-base.sh` — they cannot be represented as flat package arrays and are too coupled to ordering logic.
- **Context path is `/run/context/`**, not `/ctx/` as in bluefin. Any reference to build scripts inside a `RUN` step must use `/run/context/build_scripts/...`.
- **`versionlock_gnome` must stay in sync with GNOME 50 COPR.** If a package is added to the GNOME 50 COPR repo, it likely needs a versionlock entry to prevent the EL10 base version from winning on reinstall.
- **CentOS Stream 10 uses `dnf` not `dnf5`.** Do not copy `dnf5`-specific flags from the bluefin (Fedora) scripts.

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| `read-packages: section 'X' not found` | Wrong section name in TOML | Check section names in `base.toml` |
| Package not found during `dnf install` | Package not in base/EPEL, needs COPR | Add COPR enablement in the shell script |
| GNOME 50 component downgraded | Missing versionlock entry | Add to `[versionlock_gnome]` |
| `tomllib` import error | Python < 3.11 in build container | CentOS Stream 10 ships Python 3.12 — should not occur |
