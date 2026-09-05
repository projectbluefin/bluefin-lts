#!/usr/bin/env bash

set -xeuo pipefail

if ! grep -q "kms-modifiers" /usr/share/glib-2.0/schemas/zz1-bluefin-lts-shell.gschema.override; then
    sed -i "/experimental-features/ s/\]/, 'kms-modifiers'&/" /usr/share/glib-2.0/schemas/zz1-bluefin-lts-shell.gschema.override
fi
echo "Compiling gschema to include bluefin setting overrides"
glib-compile-schemas /usr/share/glib-2.0/schemas
