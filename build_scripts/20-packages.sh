#!/bin/bash

set -xeuo pipefail

dnf -y remove \
	setroubleshoot

dnf -y install \
	-x gnome-extensions-app \
	NetworkManager-openconnect-gnome \
	NetworkManager-openvpn-gnome \
	btrfs-progs \
	buildah \
	containerd \
	ddcutil \
	distrobox \
	fastfetch \
	firewalld \
	flatpak \
	fpaste \
	fzf \
	glow \
	gnome-disk-utility \
	gum \
	hplip \
	ibus-chewing \
	jetbrains-mono-fonts-all \
	jxl-pixbuf-loader \
	just \
	nss-mdns \
	ntfs-3g \
	papers-thumbnailer \
	pcsc-lite \
	powertop \
	rclone \
	restic \
	system-reinstall-bootc \
	tuned-ppd \
	wireguard-tools \
	wl-clipboard \
	xdg-terminal-exec \
	xhost
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

# This is required so homebrew works indefinitely.
# Symlinking it makes it so whenever another GCC version gets released it will break if the user has updated it without-
# the homebrew package getting updated through our builds.
# We could get some kind of static binary for GCC but this is the cleanest and most tested alternative. This Sucks.
dnf -y --setopt=install_weak_deps=False install gcc

# Versionlock GNOME 50 components to prevent downgrades to EL10 base versions
dnf versionlock add gnome-shell gdm mutter gnome-session-wayland-session \
    gnome-settings-daemon gnome-control-center gsettings-desktop-schemas \
    gtk4 libadwaita pango fontconfig selinux-policy selinux-policy-targeted gnutls
