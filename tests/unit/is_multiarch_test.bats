#!/usr/bin/env bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
IS_MULTIARCH="${SCRIPT_DIR}/../../scripts/is-multiarch.sh"

@test "is-multiarch: script exists and is executable" {
    [ -x "${IS_MULTIARCH}" ]
}

@test "is-multiarch: accepts valid OCI image index with amd64 and arm64" {
    manifest='{
      "schemaVersion": 2,
      "mediaType": "application/vnd.oci.image.index.v1+json",
      "manifests": [
        {"platform": {"architecture": "amd64", "os": "linux"}},
        {"platform": {"architecture": "arm64", "os": "linux"}}
      ]
    }'
    run "${IS_MULTIARCH}" "${manifest}"
    [ "$status" -eq 0 ]
}

@test "is-multiarch: accepts valid Docker manifest list with amd64 and arm64 via stdin" {
    manifest='{
      "schemaVersion": 2,
      "mediaType": "application/vnd.docker.distribution.manifest.list.v2+json",
      "manifests": [
        {"platform": {"architecture": "arm64", "os": "linux"}},
        {"platform": {"architecture": "amd64", "os": "linux"}}
      ]
    }'
    run bash -c "echo '${manifest}' | '${IS_MULTIARCH}'"
    [ "$status" -eq 0 ]
}

@test "is-multiarch: rejects single-architecture manifest" {
    manifest='{
      "schemaVersion": 2,
      "mediaType": "application/vnd.oci.image.manifest.v1+json",
      "config": {}
    }'
    run "${IS_MULTIARCH}" "${manifest}"
    [ "$status" -ne 0 ]
}

@test "is-multiarch: rejects index missing arm64" {
    manifest='{
      "schemaVersion": 2,
      "mediaType": "application/vnd.oci.image.index.v1+json",
      "manifests": [
        {"platform": {"architecture": "amd64", "os": "linux"}}
      ]
    }'
    run "${IS_MULTIARCH}" "${manifest}"
    [ "$status" -ne 0 ]
}

@test "is-multiarch: rejects empty or non-JSON input" {
    run "${IS_MULTIARCH}" ""
    [ "$status" -ne 0 ]
    run "${IS_MULTIARCH}" "not-json"
    [ "$status" -ne 0 ]
}
