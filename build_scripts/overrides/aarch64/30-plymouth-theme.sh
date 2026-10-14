#!/usr/bin/env bash

set -xeuo pipefail

# On aarch64, plymouth modules install to /usr/lib/plymouth but plymouth
# looks in /usr/lib64/plymouth. Create symlink to fix module loading.
echo "=== Plymouth libdir fix ==="
echo "Architecture: $(uname -m)"
echo "Checking /usr/lib64:"
ls -ld /usr/lib64 2>/dev/null || echo "  /usr/lib64 does not exist"
echo "Checking /usr/lib/plymouth:"
ls -ld /usr/lib/plymouth 2>/dev/null || echo "  /usr/lib/plymouth does not exist"

# Ensure /usr/lib64 exists
if [ ! -d /usr/lib64 ]; then
	echo "Creating /usr/lib64 directory"
	mkdir -p /usr/lib64
fi

# Create symlink if it doesn't exist
if [ ! -e /usr/lib64/plymouth ]; then
	echo "Creating symlink /usr/lib64/plymouth -> /usr/lib/plymouth"
	ln -sv /usr/lib/plymouth /usr/lib64/plymouth
else
	echo "/usr/lib64/plymouth already exists:"
	ls -la /usr/lib64/plymouth
fi

echo "Verifying script.so:"
ls -la /usr/lib64/plymouth/script.so 2>/dev/null || echo "  script.so NOT FOUND in /usr/lib64/plymouth"
ls -la /usr/lib/plymouth/script.so 2>/dev/null || echo "  script.so NOT FOUND in /usr/lib/plymouth"

# Set the plymouth theme to uranium
plymouth-set-default-theme uranium
