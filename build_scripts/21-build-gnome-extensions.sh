#!/usr/bin/bash

set -eoux pipefail

echo "::group:: ===$(basename "$0")==="

# Install tooling
dnf -y install glib2-devel meson sassc cmake dbus-devel

# Build Extensions

# AppIndicator Support
glib-compile-schemas --strict /usr/share/gnome-shell/extensions/appindicatorsupport@rgcjonas.gmail.com/schemas

# Bazaar Companion
mv /usr/share/gnome-shell/extensions/tmp/bazaar-integration@kolunmi.github.io/src/ /usr/share/gnome-shell/extensions/bazaar-integration@kolunmi.github.io/

# Blur My Shell
make -C /usr/share/gnome-shell/extensions/blur-my-shell@aunetx
unzip -o /usr/share/gnome-shell/extensions/blur-my-shell@aunetx/build/blur-my-shell@aunetx.shell-extension.zip -d /usr/share/gnome-shell/extensions/blur-my-shell@aunetx
glib-compile-schemas --strict /usr/share/gnome-shell/extensions/blur-my-shell@aunetx/schemas
rm -rf /usr/share/gnome-shell/extensions/blur-my-shell@aunetx/build

# Caffeine
# The Caffeine extension is built/packaged into a temporary subdirectory (tmp/caffeine/caffeine@patapon.info).
# Unlike other extensions, it must be moved to the standard extensions directory so GNOME Shell can detect it.
mv /usr/share/gnome-shell/extensions/tmp/caffeine/caffeine@patapon.info /usr/share/gnome-shell/extensions/caffeine@patapon.info
glib-compile-schemas --strict /usr/share/gnome-shell/extensions/caffeine@patapon.info/schemas

# Dash to Dock
make -C /usr/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com
glib-compile-schemas --strict /usr/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/schemas

# Gradia Capture
bash /usr/share/gnome-shell/extensions/gradia-integration@alexandervanhee.github.io/build.sh
unzip -o /usr/share/gnome-shell/extensions/gradia-integration@alexandervanhee.github.io/gradia-integration@alexandervanhee.github.io.shell-extension.zip -d /usr/share/gnome-shell/extensions/gradia-integration@alexandervanhee.github.io
rm -f /usr/share/gnome-shell/extensions/gradia-integration@alexandervanhee.github.io/gradia-integration@alexandervanhee.github.io.shell-extension.zip
glib-compile-schemas --strict /usr/share/gnome-shell/extensions/gradia-integration@alexandervanhee.github.io/schemas

# GSConnect
meson setup --prefix=/usr /usr/share/gnome-shell/extensions/gsconnect@andyholmes.github.io /usr/share/gnome-shell/extensions/gsconnect@andyholmes.github.io/_build
meson install -C /usr/share/gnome-shell/extensions/gsconnect@andyholmes.github.io/_build --skip-subprojects
# GSConnect installs schemas to /usr/share/glib-2.0/schemas and meson compiles them automatically

# Custom Command Menu
glib-compile-schemas --strict /usr/share/gnome-shell/extensions/custom-command-list@storageb.github.com/schemas

# Search Light
glib-compile-schemas --strict /usr/share/gnome-shell/extensions/search-light@icedman.github.com/schemas

# Quick Settings Audio Panel
# Ships as a prebuilt .shell-extension.zip release asset (no source build required).
# Version is pinned in image-versions.yaml and tracked by Renovate.
QSAP_UUID="quick-settings-audio-panel@rayzeq.github.io"
QSAP_VERSION=$(grep '^\s*quick_settings_audio_panel:' /run/context/image-versions.yaml | sed 's/.*"\(.*\)".*/\1/')
QSAP_DIR="/usr/share/gnome-shell/extensions/${QSAP_UUID}"
mkdir -p "${QSAP_DIR}"
curl -fsSL "https://github.com/Rayzeq/quick-settings-audio-panel/releases/download/${QSAP_VERSION}/${QSAP_UUID}.shell-extension.zip" \
    -o /tmp/qsap.shell-extension.zip
unzip -o /tmp/qsap.shell-extension.zip -d "${QSAP_DIR}"
rm -f /tmp/qsap.shell-extension.zip
glib-compile-schemas --strict "${QSAP_DIR}/schemas"
install -Dm644 "${QSAP_DIR}/schemas/org.gnome.shell.extensions.quick-settings-audio-panel.gschema.xml" \
    "/usr/share/glib-2.0/schemas/org.gnome.shell.extensions.quick-settings-audio-panel.gschema.xml"

# BudsLink Companion
# GNOME panel extension companion for the BudsLink flatpak app (Dakota port #1512).
# Vendored as a submodule pinned to the maniacx/BudsLink-Companion Gnome-Extension branch;
# the extension files already live in-place under the extensions dir, so this only
# compiles its schema and publishes it to the global schema path.
BL_UUID="BudsLink-Companion@maniacx.github.com"
BL_DIR="/usr/share/gnome-shell/extensions/${BL_UUID}"
glib-compile-schemas --strict "${BL_DIR}/schemas"
install -Dm644 "${BL_DIR}/schemas/org.gnome.shell.extensions.BudsLink-Companion.gschema.xml" \
    "/usr/share/glib-2.0/schemas/org.gnome.shell.extensions.BudsLink-Companion.gschema.xml"

# Vicinae Launcher
# Minimalist app launcher (Dakota port #1515). Pinned GitHub release tarball, tracked by Renovate.
# Vicinae ships x86_64-only (upstream publishes no aarch64/arm64 build); guard the whole block
# like 99-flatpaks.sh does so the aarch64 build is not aborted by curl -fsSL on a 404.
ARCH=$(arch)
if [ "$ARCH" != "aarch64" ]; then
    mkdir -p /tmp/vicinae
    VICINAE_VERSION=$(grep '^\s*vicinae:' /run/context/image-versions.yaml | sed 's/.*"\(.*\)".*/\1/')
    curl -fsSL "https://github.com/vicinaehq/vicinae/releases/download/${VICINAE_VERSION}/vicinae-linux-x86_64-${VICINAE_VERSION}.tar.gz" \
        -o /tmp/vicinae.tar.gz
    tar -xzf /tmp/vicinae.tar.gz -C /tmp/vicinae
    install -Dm755 /tmp/vicinae/bin/vicinae /usr/bin/vicinae
    for f in /tmp/vicinae/libexec/vicinae/*; do
        install -Dm755 "$f" "/usr/libexec/vicinae/$(basename "$f")"
    done
    install -Dm644 /tmp/vicinae/share/applications/vicinae.desktop "/usr/share/applications/vicinae.desktop"
    install -Dm644 /tmp/vicinae/share/applications/vicinae-url-handler.desktop "/usr/share/applications/vicinae-url-handler.desktop"
    install -Dm644 /tmp/vicinae/share/icons/hicolor/512x512/apps/vicinae.png "/usr/share/icons/hicolor/512x512/apps/vicinae.png"
    install -Dm644 /tmp/vicinae/lib/systemd/user/vicinae.service "/usr/lib/systemd/user/vicinae.service"
    install -Dm644 /tmp/vicinae/lib/modules-load.d/vicinae.conf "/usr/lib/modules-load.d/vicinae.conf"
    # Vicinae ships 49 TOML themes (+ icons) under share/vicinae/themes; install the whole
    # tree so the launcher has themes to enumerate instead of shipping themeless.
    mkdir -p /usr/share/vicinae/themes
    cp -a /tmp/vicinae/share/vicinae/themes/. /usr/share/vicinae/themes/
    # Starts the ~33 MB vicinae-server (Restart=always) in every graphical session, whether
    # or not the user launches Vicinae. Intentional: it provides the paste-over-clipboard
    # service the launcher documents; move the symlink to opt in if that is unwanted.
    mkdir -p "/usr/lib/systemd/user/graphical-session.target.wants"
    ln -sfn ../vicinae.service "/usr/lib/systemd/user/graphical-session.target.wants/vicinae.service"
    rm -rf /tmp/vicinae
fi

rm /usr/share/glib-2.0/schemas/gschemas.compiled
glib-compile-schemas /usr/share/glib-2.0/schemas

# Cleanup
dnf -y remove glib2-devel meson sassc cmake dbus-devel
rm -rf /usr/share/gnome-shell/extensions/tmp

echo "::endgroup::"
