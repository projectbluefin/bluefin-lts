#!/usr/bin/env bash

set -xeuo pipefail

echo "Compiling NVIDIA gschema overrides"
glib-compile-schemas /usr/share/glib-2.0/schemas
