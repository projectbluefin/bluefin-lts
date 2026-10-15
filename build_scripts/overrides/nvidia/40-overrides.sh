#!/usr/bin/env bash

set -xeuo pipefail

sed -i "/experimental-features/ s/\]/, 'kms-modifiers'&/" /usr/share/glib-2.0/schemas/zz0-thallium-modifications.gschema.override
echo "Compiling gschema to include thallium setting overrides"
glib-compile-schemas /usr/share/glib-2.0/schemas
