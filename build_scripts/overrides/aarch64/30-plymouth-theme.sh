#!/usr/bin/env bash

set -xeuo pipefail

# On aarch64, plymouth modules are in /usr/lib/plymouth but plymouth looks in /usr/lib64/plymouth
if [ ! -d /usr/lib64/plymouth ] && [ -d /usr/lib/plymouth ]; then
	ln -s /usr/lib/plymouth /usr/lib64/plymouth
fi

# Set the plymouth theme to uranium
plymouth-set-default-theme uranium
