# Uranium

> NOTE: This once was Project Bluefin's LTS it's still close to the original just different branding.

[![Build Uranium](https://github.com/thallium-suite/uranium/actions/workflows/build-regular.yml/badge.svg)](https://github.com/thallium-suite/uranium/actions/workflows/build-regular.yml)

Long-term support desktop built on CentOS Stream 10 for longer support windows, conservative upgrades, and production-focused workstations.

![image](https://github.com/user-attachments/assets/2e160934-44e6-4aee-b2b8-accb3bcf0a41)

## Images

### Uranium

Long-term support stream built on CentOS Stream 10.

```bash
# LTS — recommended
sudo bootc switch ghcr.io/thallium-suite/uranium:stable --enforce-container-sigpolicy
# LTS — NVIDIA
sudo bootc switch ghcr.io/thallium-suite/uranium-nvidia:stable --enforce-container-sigpolicy
```

## Migrating

Uranium is published at a new registry path, so existing installs keep
receiving updates from their current image reference and **will not** be moved
automatically. There is no automatic migration: switch explicitly.

| Previous image | Current image |
|---|---|
| `ghcr.io/projectbluefin/bluefin-lts:stable` | `ghcr.io/thallium-suite/uranium:stable` |
| `ghcr.io/projectbluefin/bluefin-lts-nvidia:stable` | `ghcr.io/thallium-suite/uranium-nvidia:stable` |
| `ghcr.io/ublue-os/bluefin:lts` (legacy) | `ghcr.io/thallium-suite/uranium:stable` |
| `ghcr.io/ublue-os/bluefin-dx:lts` (legacy) | `ghcr.io/thallium-suite/uranium:stable` + run `ujust devmode` after reboot |
| `ghcr.io/ublue-os/bluefin-gdx:lts` (legacy) | `ghcr.io/thallium-suite/uranium-nvidia:stable` + run `ujust devmode` after reboot |
| arm64 variants | No in-place migration — reinstall from the current image |

```bash
sudo bootc switch ghcr.io/thallium-suite/uranium:stable --enforce-container-sigpolicy
```

Rebasing between the Fedora-based Amotic family and Uranium is not supported.
Plan migrations as fresh installs or supported upgrade paths.

## Community

Uranium has no community infrastructure of its own yet. Until it does, use this
repository's [issue tracker](https://github.com/thallium-suite/uranium/issues)

## Contributing

See the **[Contributing Guide](https://docs.projectbluefin.io/contributing/)** for how to get involved. All participants are expected to follow the [Universal Blue Community Guidelines](https://docs.projectbluefin.io/contributing#community-guidelines).

Report security vulnerabilities via [SECURITY.md](SECURITY.md).

## License

Apache License 2.0 — see [LICENSE](LICENSE).

Uranium incorporates [CentOS Stream](https://www.centos.org/centos-stream/), [GNOME](https://www.gnome.org/), [Universal Blue](https://universal-blue.org/), and various CNCF projects, each under their respective licenses.
