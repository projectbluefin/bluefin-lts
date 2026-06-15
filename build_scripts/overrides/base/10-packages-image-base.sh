#!/usr/bin/env bash

set -xeuo pipefail

# shellcheck disable=SC2034
ARCH=$(uname -m)

READ_PKGS="python3 /run/context/build_scripts/scripts/read-packages"
PKGS_TOML="/run/context/build_scripts/packages/base.toml"

# This is the base for a minimal GNOME 50 system on CentOS Stream.

# This thing slows down downloads A LOT for no reason
# --setopt=tsflags=noscripts skips postun/preun scriptlets (rhc's postun crashes
# in container build context — tries to stop services that don't exist).
dnf remove -y --setopt=tsflags=noscripts subscription-manager
dnf -y install 'dnf-command(versionlock)'

/run/context/build_scripts/scripts/kernel-swap.sh

# GNOME 50 repo file
# libjxl 0.11 in this repo has a different ABI than EPEL's 0.10, which breaks
# epel-multimedia's libavcodec (needs libjxl.so.0.10). Exclude it so EPEL wins.
dnf config-manager --add-repo "https://copr.fedorainfracloud.org/coprs/jreilly1821/c10s-gnome-50/repo/epel-${MAJOR_VERSION_NUMBER}/jreilly1821-c10s-gnome-50-epel-${MAJOR_VERSION_NUMBER}.repo"
GNOME50_REPO=$(find /etc/yum.repos.d/ -name "*jreilly1821*gnome-50*" | head -1)
echo "exclude=libjxl*" >> "${GNOME50_REPO}"

# These upgrades MUST happen before the GNOME group install.
# - glib2: EL10 ships 2.80.x; GNOME 50 requires newer API symbols.
# - fontconfig: COPR pango 1.57+ links FcConfigSetDefaultSubstitute (added in
#   fontconfig 2.17.0); EL10 base ships 2.15.0 — causes a symbol lookup error
#   at gnome-shell startup.
# - selinux-policy: COPR 43.x is required for GDM 50 userdb varlink socket
#   architecture; EL10 base 42.x lacks the necessary policy rules.
# - gnutls: newer glib2 from COPR may depend on gnutls symbols not in base.
dnf -y install selinux-policy selinux-policy-targeted gnutls
dnf -y upgrade glib2 fontconfig

# Please, dont remove this as it will break everything GNOME related
dnf versionlock add glib2 fontconfig

# This fixes a lot of skew issues on nvidia because kernel-devel wont update then
dnf versionlock add kernel kernel-devel kernel-devel-matched kernel-core kernel-modules kernel-modules-core kernel-modules-extra kernel-uki-virt

dnf -y install "https://dl.fedoraproject.org/pub/epel/epel-release-latest-${MAJOR_VERSION_NUMBER}.noarch.rpm"
dnf config-manager --set-enabled crb

# Multimidia codecs
dnf config-manager --add-repo=https://negativo17.org/repos/epel-multimedia.repo
dnf config-manager --set-disabled epel-multimedia
dnf -y install --enablerepo=epel-multimedia \
	ffmpeg libavcodec @multimedia gstreamer1-plugins-{bad-free,bad-free-libs,good,base} lame{,-libs} libjxl ffmpegthumbnailer

# `dnf group info Workstation` without GNOME
dnf group install -y --nobest \
	-x rsyslog* \
	-x cockpit \
	-x cronie* \
	-x crontabs \
	-x PackageKit \
	-x PackageKit-command-not-found \
	"Common NetworkManager submodules" \
	"Core" \
	"Fonts" \
	"Guest Desktop Agents" \
	"Hardware Support" \
	"Printing Client" \
	"Standard" \
	"Workstation product core"

# Minimal GNOME group. ("Multimedia" adds most of the packages from the GNOME group. This should clear those up too.)
# In order to reproduce this, get the packages with `dnf group info GNOME`, install them manually with dnf install and see all the packages that are already installed.
# Other than that, I've removed a few packages we didnt want, those being a few GUI applications.
readarray -t GNOME_PKGS    < <($READ_PKGS "$PKGS_TOML" gnome)
readarray -t GNOME_EXCL    < <($READ_PKGS "$PKGS_TOML" gnome_excluded)
GNOME_EXCLUDE_ARGS=()
for pkg in "${GNOME_EXCL[@]}"; do GNOME_EXCLUDE_ARGS+=(-x "$pkg"); done
dnf -y install "${GNOME_EXCLUDE_ARGS[@]}" "${GNOME_PKGS[@]}"

dnf -y install \
	plymouth \
	plymouth-system-theme \
	fwupd \
	systemd-{resolved,container,oomd} \
	libcamera{,-{v4l2,gstreamer,tools}}

dnf -y install gnome50-el10-compat libgda

# This package adds "[systemd] Failed Units: *" to the bashrc startup
dnf -y remove console-login-helper-messages

# We need to remove centos-logos before applying bluefin's logos and after installing this package. Do not remove this!
rpm --erase --nodeps centos-logos
# HACK: There currently is no generic-logos equivalent like on Fedora
# We need this so packages like anaconda don't replace our logos by pulling in centos-logos again
dnf -y install https://kojipkgs.fedoraproject.org//packages/generic-logos/18.0.0/26.fc43/noarch/generic-logos-18.0.0-26.fc43.noarch.rpm
rpm --erase --nodeps --nodb generic-logos
