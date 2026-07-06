#!/usr/bin/env bash

set -xeuo pipefail

FLAVOR="nvidia"
IMAGE_NAME="bluefin-lts-${FLAVOR}"
IMAGE_REF="ostree-image-signed:docker://ghcr.io/${IMAGE_VENDOR}/bluefin-lts-${FLAVOR}"
export FLAVOR
export IMAGE_NAME
export IMAGE_REF
"${SCRIPTS_PATH}/image-info-set"
