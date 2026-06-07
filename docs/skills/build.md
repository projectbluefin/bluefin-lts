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

## Core builds

| Goal | Command | Typical time |
|---|---|---|
| Regular | `just build bluefin lts 0 0 0` | 45-90 min |
| GDX | `just build bluefin lts 0 1 0` | 45-90 min |
| HWE | `just build bluefin lts 0 0 1` | 45-90 min |

The `gnome_version` parameter defaults to `"50"`. Override only if testing a future GNOME version.

**HWE and GDX kernel tracking:** For HWE and GDX builds, the Fedora CoreOS stable version is resolved dynamically at build time via `skopeo inspect docker://quay.io/fedora/fedora-coreos:stable`. This version is used to select the matching `coreos-stable-<version>` akmods image tag and is passed as `FEDORA_AKMODS_VERSION` (controls negativo17 Fedora repo for NVIDIA drivers). Override with `COREOS_STABLE_VERSION` env var if you need to pin:

```bash
COREOS_STABLE_VERSION=44 just build bluefin lts 0 1 0   # GDX, force Fedora 44 akmods
COREOS_STABLE_VERSION=44 just build bluefin lts 0 0 1   # HWE, force Fedora 44 akmods
```

Regular builds continue to use `centos-10` akmods and the `fedora_akmods_version` parameter (default `"43"`) has no effect on HWE/GDX.

**Never cancel builds.** Use 120+ minute timeouts.

## Variant map

| Variant | What changes |
|---|---|
| Regular | base LTS image |
| GDX | GPU / AI tooling (NVIDIA) |
| HWE | newer hardware enablement |

## VM / disk artifacts

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

## Debugging checklist

| Symptom | Check |
|---|---|
| build fails early | `just check && just lint` |
| missing command | `which just podman git` |
| package pulls fail | repo/network timeout; retry after failure completes naturally |
| storage errors | run `just clean`, verify free disk |
| permission issues | some build paths require sudo/root; `gen-sbom` runs as root — `sbom_out/` is chowned back to runner after write |
| NVIDIA driver version mismatch in GDX | Set `COREOS_STABLE_VERSION=NN` to pin; or let it auto-resolve from CoreOS stable |

Recovery loop:

```bash
just clean
just check && just lint
just build bluefin lts
```
