#!/bin/bash

set -xeuo pipefail

READ_PKGS="python3 /run/context/build_scripts/scripts/read-packages"
PKGS_TOML="/run/context/build_scripts/packages/base.toml"

# Remove packages that conflict with image content
readarray -t REMOVE_PKGS < <($READ_PKGS "$PKGS_TOML" remove)
dnf -y remove "${REMOVE_PKGS[@]}"

# Main package install from base/EPEL repos
readarray -t INSTALL_PKGS    < <($READ_PKGS "$PKGS_TOML" install)
readarray -t EXCLUDED_PKGS   < <($READ_PKGS "$PKGS_TOML" install_excluded)

EXCLUDE_ARGS=()
for pkg in "${EXCLUDED_PKGS[@]}"; do
    EXCLUDE_ARGS+=(-x "$pkg")
done

dnf -y install \
    "${EXCLUDE_ARGS[@]}" \
    "${INSTALL_PKGS[@]}"

rm -rf /usr/share/doc/just

# Everything that depends on external repositories should be after this.
# Make sure to set them as disabled and enable them only when you are going to use their packages.
# We do, however, leave crb and EPEL enabled by default.

dnf config-manager --add-repo "https://pkgs.tailscale.com/stable/centos/${MAJOR_VERSION_NUMBER}/tailscale.repo"
dnf config-manager --set-disabled "tailscale-stable"
# FIXME: tailscale EPEL10 request: https://bugzilla.redhat.com/show_bug.cgi?id=2349099
dnf -y --enablerepo "tailscale-stable" install \
    tailscale

# Install uupd from GitHub release tarball.
# The ublue-os/packages COPR no longer has an epel-10 chroot (removed ~2026-06-08).
# Version is pinned in image-versions.yaml and tracked by Renovate.
# yq is not available in the CentOS build container — parse with grep/sed
UUPD_VERSION=$(grep '^\s*uupd:' /run/context/image-versions.yaml | sed 's/.*"\(.*\)".*/\1/')
curl -fsSL "https://github.com/ublue-os/uupd/releases/download/${UUPD_VERSION}/uupd_Linux_x86_64.tar.gz" \
    | tar -xzf - -C /usr/bin uupd
chmod 0755 /usr/bin/uupd
# The tarball only ships the binary; download the systemd units from source too.
UUPD_RAW="https://raw.githubusercontent.com/ublue-os/uupd/${UUPD_VERSION}"
curl -fsSL "${UUPD_RAW}/uupd.service" -o /usr/lib/systemd/system/uupd.service
curl -fsSL "${UUPD_RAW}/uupd.timer"   -o /usr/lib/systemd/system/uupd.timer

# This is required so homebrew works indefinitely.
# Symlinking it makes it so whenever another GCC version gets released it will break if the user has updated it without-
# the homebrew package getting updated through our builds.
# We could get some kind of static binary for GCC but this is the cleanest and most tested alternative. This Sucks.
dnf -y --setopt=install_weak_deps=False install gcc

# Versionlock GNOME 50 components to prevent downgrades to EL10 base versions
readarray -t VERSIONLOCK_PKGS < <($READ_PKGS "$PKGS_TOML" versionlock_gnome)
dnf versionlock add "${VERSIONLOCK_PKGS[@]}"
