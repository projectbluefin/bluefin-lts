#!/usr/bin/env bash
# is-multiarch.sh: checks if a container manifest JSON is a multi-arch index containing amd64 and arm64.
# Accepts raw manifest JSON via argument ($1) or stdin.
set -euo pipefail

raw="${1:-}"
if [[ -z "$raw" ]]; then
    raw="$(cat)"
fi

if [[ -z "$raw" ]]; then
    exit 1
fi

media_type=$(jq -r '.mediaType // empty' <<<"$raw")
if [[ "$media_type" != "application/vnd.oci.image.index.v1+json" && \
      "$media_type" != "application/vnd.docker.distribution.manifest.list.v2+json" ]]; then
    exit 1
fi

jq -e '([.manifests[]?.platform.architecture] | sort) == ["amd64", "arm64"]' <<<"$raw" >/dev/null
