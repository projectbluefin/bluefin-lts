---
name: bluefin-lts-gnome-extensions
version: "1.0"
last_updated: 2026-06-23
tags: [gnome, extensions, submodules, build]
description: >-
  Adding, removing, and building GNOME Shell extensions in projectbluefin/bluefin-lts. Extensions
  are git submodules in system_files/usr/share/gnome-shell/extensions/<UUID>/. Use when adding a
  new GNOME Shell extension, removing one, debugging schema compile failures, or updating the
  build step in 21-build-gnome-extensions.sh.
metadata:
  type: procedure
---

# GNOME Shell Extensions

Extensions in bluefin-lts are **git submodules** tracked in `system_files/usr/share/gnome-shell/extensions/<UUID>/`. Renovate updates submodule digests automatically.

## Adding an extension

```bash
# 1. Find the UUID from the extension's metadata.json (.uuid field)
UUID="my-extension@author.github.io"

# 2. Add submodule
git submodule add <upstream-repo-url> \
  system_files/usr/share/gnome-shell/extensions/"${UUID}"

# 3. Add a build block to 21-build-gnome-extensions.sh (before the final glib-compile-schemas line)
# 4. If the extension needs dconf overrides, create a keyfile in system_files/etc/dconf/db/distro.d/
```

## Build block patterns

Every extension needs at minimum a `glib-compile-schemas --strict` call. Complex ones need more.

### Schema-only (most common)
```bash
glib-compile-schemas --strict /usr/share/gnome-shell/extensions/${UUID}/schemas
```

### Extensions requiring `make` (e.g. blur-my-shell, dash-to-dock)
```bash
make -C /usr/share/gnome-shell/extensions/${UUID}
# some extensions produce a zip artifact that must be unzipped back in-place:
unzip -o /usr/share/gnome-shell/extensions/${UUID}/build/${UUID}.shell-extension.zip \
  -d /usr/share/gnome-shell/extensions/${UUID}
glib-compile-schemas --strict /usr/share/gnome-shell/extensions/${UUID}/schemas
rm -rf /usr/share/gnome-shell/extensions/${UUID}/build
```

### Extensions with their own `build.sh` (e.g. gradia-integration)
```bash
bash /usr/share/gnome-shell/extensions/${UUID}/build.sh
unzip -o /usr/share/gnome-shell/extensions/${UUID}/${UUID}.shell-extension.zip \
  -d /usr/share/gnome-shell/extensions/${UUID}
rm -f /usr/share/gnome-shell/extensions/${UUID}/${UUID}.shell-extension.zip
glib-compile-schemas --strict /usr/share/gnome-shell/extensions/${UUID}/schemas
```

### Meson-based (gsconnect — special case)
```bash
meson setup --prefix=/usr \
  /usr/share/gnome-shell/extensions/${UUID} \
  /usr/share/gnome-shell/extensions/${UUID}/_build
meson install -C /usr/share/gnome-shell/extensions/${UUID}/_build --skip-subprojects
# GSConnect installs schemas to /usr/share/glib-2.0/schemas and compiles them automatically
# No explicit glib-compile-schemas call needed
```

### Extensions in a `tmp/` subdirectory (caffeine, bazaar)

Some upstream repos don't have the UUID at the top level — the actual extension lives in a subdirectory or in a `src/` dir. The submodule must be cloned into `tmp/` and moved during build:

```bash
# caffeine: UUID is inside the repo as a subdirectory
mv /usr/share/gnome-shell/extensions/tmp/caffeine/caffeine@patapon.info \
   /usr/share/gnome-shell/extensions/caffeine@patapon.info
glib-compile-schemas --strict /usr/share/gnome-shell/extensions/caffeine@patapon.info/schemas

# bazaar: actual extension code is in src/
mv /usr/share/gnome-shell/extensions/tmp/bazaar-integration@kolunmi.github.io/src/ \
   /usr/share/gnome-shell/extensions/bazaar-integration@kolunmi.github.io/
# (no schemas in this extension)
```

For `tmp/` extensions, the submodule path in `.gitmodules` is:
`system_files/usr/share/gnome-shell/extensions/tmp/<short-name>`

## Removing an extension

```bash
UUID="extension@author.github.io"
git submodule deinit -f system_files/usr/share/gnome-shell/extensions/"${UUID}"
git rm system_files/usr/share/gnome-shell/extensions/"${UUID}"
# also cleans .gitmodules entry automatically
```

Then remove the build block from `21-build-gnome-extensions.sh` and the dconf keyfile if any.

## Build tooling

`21-build-gnome-extensions.sh` installs build deps at the top and removes them at the bottom:

```bash
dnf -y install glib2-devel meson sassc cmake dbus-devel
# ... all build blocks ...
dnf -y remove glib2-devel meson sassc cmake dbus-devel
rm -rf /usr/share/gnome-shell/extensions/tmp
```

The final global schema recompile is also in this script:
```bash
rm /usr/share/glib-2.0/schemas/gschemas.compiled
glib-compile-schemas /usr/share/glib-2.0/schemas
```
Do not remove this step — it regenerates the system schemas DB after all per-extension compiles.

## dconf overrides

If an extension needs preconfigured defaults, create a keyfile:

```
system_files/etc/dconf/db/distro.d/<NN>-bluefin-lts-<short-name>
```

Example path: `system_files/etc/dconf/db/distro.d/05-bluefin-lts-custom-command-menu`

Use numeric prefix to control override priority. Higher numbers win.

## Validation

```bash
just check && just lint
```

Both must exit 0. `just lint` runs shellcheck on `build_scripts/**/*.sh` including the extensions build script.
