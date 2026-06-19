#!/usr/bin/env bash

set -xeuo pipefail

FLAVOR="nvidia"
IMAGE_NAME="bluefin-lts-hwe-${FLAVOR}"
IMAGE_REF="ostree-image-signed:docker://ghcr.io/${IMAGE_VENDOR}/bluefin-lts-hwe-${FLAVOR}"
export FLAVOR
export IMAGE_NAME
export IMAGE_REF
"${SCRIPTS_PATH}/image-info-set"
