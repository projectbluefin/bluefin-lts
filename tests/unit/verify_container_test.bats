#!/usr/bin/env bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
JUSTFILE="${REPO_ROOT}/Justfile"

@test "verify-container: recipe exists in Justfile" {
    grep -qE '^verify-container container=' "${JUSTFILE}"
}

@test "verify-container: build recipe invokes verify-container with keyless for common image" {
    run grep -A 8 'build \$target_image' "${JUSTFILE}"
    [ "$status" -eq 0 ]
    grep -q 'verify-container "common:latest@\${common_image_sha}" ghcr.io/projectbluefin "keyless"' "${JUSTFILE}"
}

@test "verify-container: keyless branch explicitly checks key == keyless" {
    grep -q 'if \[\[ "\${key}" == "keyless" \]\]; then' "${JUSTFILE}"
}

@test "verify-container: pins cosign version and verifies sha256 checksums" {
    grep -q 'COSIGN_VERSION="v3.1.1"' "${JUSTFILE}"
    grep -q 'COSIGN_SHA256="ae1ecd212663f3693ad9edf8b1a183900c9a52d3155ba6e354237f9a0f6463fc"' "${JUSTFILE}"
    grep -q 'COSIGN_SHA256="2ec865872e331c32fd12b08dae15332d3f92c0aa029219589684a4903ca85d11"' "${JUSTFILE}"
    grep -q 'cosign_checksums.txt' "${JUSTFILE}"
}

@test "verify-container: no unused public keys vendored in keys/" {
    if [ -d "${REPO_ROOT}/keys" ]; then
        run find "${REPO_ROOT}/keys" -name "*.pub"
        [ "$output" = "" ]
    fi
}
