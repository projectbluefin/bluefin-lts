#!/usr/bin/env bash

set -xeuo pipefail

FASTFETCH_CONFIG="/usr/share/thallium-os/fastfetch.jsonc"
GSCHEMA_OVERRIDE="/usr/share/glib-2.0/schemas/zz0-thallium-modifications.gschema.override"

# Both paths are owned by thallium-suite/common. Assert them before touching
# either: a missing file makes `sed -i` fail with an opaque "No such file",
# and these two are the files the whole branding story hangs on.
test -f "${FASTFETCH_CONFIG}"
test -f "${GSCHEMA_OVERRIDE}"

# The fastfetch layout used to carry a Nerd Font glyph that rendered as a tofu
# box on stock terminals, so it was swapped for one that does not. The current
# layout draws its own ASCII logo and carries no such glyph, so the swap went
# away with it rather than staying as a sed that silently matched nothing.

# Automatic wallpaper changing by month.
#
# The override ships pointing at the branding repo's 06-*.xml wallpaper. Swap
# the two-digit month for the build month so a rebuild in, say, November ships
# the November wallpaper. The previous form searched for a literal "12" and so
# never matched the "06" actually present -- every build silently shipped June.
BUILD_MONTH="$(date +%m)"
sed -i -E "/^picture-uri/ s|0[0-9]-thallium\.xml|${BUILD_MONTH}-thallium.xml|" \
    "${GSCHEMA_OVERRIDE}"
# Fail loudly if the substitution did not happen: a rename in the branding repo
# would otherwise ship an image pointing at a wallpaper that is not there, with
# a black background and no diagnostic anywhere.
#
# The month is read back out of the file rather than grepped for as part of a
# literal path. A pattern naming /usr/share/backgrounds/... would be rewritten
# by any test that sandboxes absolute paths, which silently turns this
# assertion into a test of the test harness. Comparing the two-digit month
# keeps the check path-agnostic.
WALLPAPER_MONTH="$(sed -nE "s|^picture-uri='.*/([0-9]{2})-thallium[.]xml'$|\\1|p" \
    "${GSCHEMA_OVERRIDE}" | head -1)"
if [ "${WALLPAPER_MONTH}" != "${BUILD_MONTH}" ]; then
    echo "26-packages-post: wallpaper month is '${WALLPAPER_MONTH}', expected '${BUILD_MONTH}'." >&2
    echo "  The branding repo must ship NN-thallium.xml wallpapers under the backgrounds dir." >&2
    exit 1
fi
glib-compile-schemas /usr/share/glib-2.0/schemas

# Rebuild gdk-pixbuf loader cache so all installed loaders are registered
gdk-pixbuf-query-loaders-64 --update-cache

# Add Flathub by default
mkdir -p /etc/flatpak/remotes.d
curl --retry 3 -o /etc/flatpak/remotes.d/flathub.flatpakrepo "https://dl.flathub.org/repo/flathub.flatpakrepo"

# There is no `-defaults` subpackage on c10s
curl --fail --silent --show-error --location \
  --retry 10 --retry-all-errors --retry-delay 5 \
  -o /usr/lib/systemd/zram-generator.conf \
  "https://src.fedoraproject.org/rpms/zram-generator/raw/rawhide/f/zram-generator.conf"
grep -F -e "zram-size =" /usr/lib/systemd/zram-generator.conf

# https://src.fedoraproject.org/rpms/firewalld/blob/rawhide/f/firewalld.spec
curl --fail --silent --show-error --location \
  --retry 10 --retry-all-errors --retry-delay 5 \
  -o /usr/lib/firewalld/zones/FedoraWorkstation.xml \
  "https://src.fedoraproject.org/rpms/firewalld/raw/rawhide/f/FedoraWorkstation.xml"
grep -F -e '<port protocol="udp" port="1025-65535"/>' /usr/lib/firewalld/zones/FedoraWorkstation.xml

# https://src.fedoraproject.org/rpms/firewalld/blob/rawhide/f/firewalld.spec#_178
sed -i 's|^DefaultZone=.*|DefaultZone=FedoraWorkstation|g' /etc/firewalld/firewalld.conf
sed -i 's|^IPv6_rpfilter=.*|IPv6_rpfilter=loose|g' /etc/firewalld/firewalld.conf
grep -F -e "DefaultZone=FedoraWorkstation" /etc/firewalld/firewalld.conf
grep -F -e "IPv6_rpfilter=loose" /etc/firewalld/firewalld.conf

# shellcheck disable=SC2012
depmod -a "$(ls -1 /lib/modules/ | tail -1)"

# Generate initramfs image after installing Bluefin branding because of Plymouth subpackage
# Add resume module so that hibernation works
echo "add_dracutmodules+=\" resume \"" >/etc/dracut.conf.d/resume.conf
KERNEL_SUFFIX=""
QUALIFIED_KERNEL="$(rpm -qa | grep -P 'kernel-(|'"$KERNEL_SUFFIX"'-)(\d+\.\d+\.\d+)' | sed -E 's/kernel-(|'"$KERNEL_SUFFIX"'-)//' | tail -n 1)"
/usr/bin/dracut --no-hostonly --kver "$QUALIFIED_KERNEL" --reproducible --tmpdir /boot --zstd -v --add ostree -f "/lib/modules/$QUALIFIED_KERNEL/initramfs.img"

# Footgun, See: https://github.com/ublue-os/main/issues/598
rm -f /usr/bin/chsh /usr/bin/lchsh

# Add linuxbrew to the list of paths usable by `sudo`
# not a sudoers.d override because we want to get updates from upstream and not break everything
sed -Ei "s/secure_path = (.*)/secure_path = \1:\/home\/linuxbrew\/.linuxbrew\/bin/" /etc/sudoers
