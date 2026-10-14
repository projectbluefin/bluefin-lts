#!/usr/bin/env bash

set -xeuo pipefail

# The uranium theme uses ModuleName=script, which requires script.so from
# the plymouth-plugin-script package. Ensure it is installed.
if [ ! -e /usr/lib64/plymouth/script.so ]; then
	dnf -y install plymouth-plugin-script
fi

# Verify script.so is present
ls -la /usr/lib64/plymouth/script.so

# Set the plymouth theme to uranium
plymouth-set-default-theme uranium
