#!/bin/bash

source /usr/lib/thallium/setup-services/libsetup.sh

version-script flatpaks privileged 1 || exit 0

set -x

# Set up Firefox default configuration
ARCH=$(arch)
if [ "$ARCH" != "aarch64" ] ; then
	PREF_DIR="/var/lib/flatpak/extension/org.mozilla.firefox.systemconfig/${ARCH}/stable/defaults/pref"
	mkdir -p "${PREF_DIR}"
	# Clear anything we shipped under an earlier name before copying the
	# current config in, so a rename does not leave two conflicting user.js
	# files behind. `*bluefin*` is kept on purpose: an in-place upgrade from
	# the pre-rebrand image still has that file on disk.
	rm -f "${PREF_DIR}"/*bluefin*.js "${PREF_DIR}"/*thallium*.js
	/usr/bin/cp -rf /usr/share/thallium-os/firefox-config/* "${PREF_DIR}/"
fi
