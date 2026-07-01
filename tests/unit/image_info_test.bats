#!/usr/bin/env bats

# Unit tests for build_scripts/90-image-info.sh
# Run with: bats tests/unit/image_info_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
IMAGE_INFO_SCRIPT="${SCRIPT_DIR}/../../build_scripts/90-image-info.sh"

setup() {
    # BATS_TEST_TMPDIR is a unique per-test directory managed by bats (available since 1.3.0).
    # Using it avoids relying on $$ for uniqueness, which is unreliable across bats versions.
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"

    mkdir -p "${STUB_BIN}"
    mkdir -p "${TEST_ROOT}/usr/share/ublue-os"
    mkdir -p "${TEST_ROOT}/usr/lib"

    # Minimal os-release for sed patching
    cat > "${TEST_ROOT}/usr/lib/os-release" <<'EOF'
NAME="CentOS Stream"
VERSION_CODENAME="Plow"
VARIANT_ID=centos-stream
PRETTY_NAME="CentOS Stream 10"
HOME_URL="https://centos.org/"
BUG_REPORT_URL="https://bugzilla.redhat.com/"
CPE_NAME="cpe:/o:centos:centos:10"
REDHAT_BUGZILLA_PRODUCT="Red Hat Enterprise Linux 10"
REDHAT_BUGZILLA_PRODUCT_VERSION=10
REDHAT_SUPPORT_PRODUCT="Red Hat Enterprise Linux"
REDHAT_SUPPORT_PRODUCT_VERSION="10"
EOF

    # Stub external commands used for badges/counts.
    # #!/usr/bin/env bash avoids reliance on /usr/bin/bash existing.
    for cmd in ghcurl jq numfmt; do
        cat > "${STUB_BIN}/${cmd}" <<'EOF'
#!/usr/bin/env bash
echo "0"
EOF
        chmod +x "${STUB_BIN}/${cmd}"
    done

    # curl stub for flathub API
    cat > "${STUB_BIN}/curl" <<'EOF'
#!/usr/bin/env bash
echo '{"installs_last_7_days": 0}'
EOF
    chmod +x "${STUB_BIN}/curl"

    # Patch absolute paths to use TEST_ROOT
    PATCHED_SCRIPT="${TEST_ROOT}/image-info-patched.sh"
    sed \
        -e "s|/usr/share/ublue-os/image-info.json|${TEST_ROOT}/usr/share/ublue-os/image-info.json|g" \
        -e "s|/usr/lib/os-release|${TEST_ROOT}/usr/lib/os-release|g" \
        -e "s|/usr/share/ublue-os/fastfetch-user-count|${TEST_ROOT}/usr/share/ublue-os/fastfetch-user-count|g" \
        -e "s|/usr/share/ublue-os/bazaar-install-count|${TEST_ROOT}/usr/share/ublue-os/bazaar-install-count|g" \
        "${IMAGE_INFO_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"
    # The badge-fetching lines (ghcurl + curl/flathub) call external APIs and
    # are not tested here; neutralise them so set -euo pipefail doesn't kill
    # the script when bats' output-capture pipe causes SIGPIPE on the stubs.
    sed -i \
        -e '/ghcurl/s/$/ || true/' \
        -e '/bazaar-install-count/s/$/ || true/' \
        "${PATCHED_SCRIPT}"
    # Export so test assertions can reference TEST_ROOT and so PATH/STUB_BIN
    # are available as env vars when composing the run command inline.
    export TEST_ROOT STUB_BIN PATCHED_SCRIPT
}

teardown() {
    # BATS_TEST_TMPDIR is auto-cleaned by bats; explicit cleanup for safety.
    rm -rf "${TEST_ROOT}"
}

# Helper: run the patched script with PATH explicitly set so stubs are found
# regardless of how bats propagates exported variables across subprocess
# boundaries. Uses `run env ...` (direct command) instead of a function wrapper
# to avoid bats function-dispatch inconsistencies with PATH export.
_run_image_info() {
    local image_name="${1:-bluefin}"
    local image_vendor="${2:-projectbluefin}"
    local major_version="${3:-10}"
    local sha="${4:-deadbeef}"

    run env \
        PATH="${STUB_BIN}:${PATH}" \
        IMAGE_NAME="${image_name}" \
        IMAGE_VENDOR="${image_vendor}" \
        MAJOR_VERSION_NUMBER="${major_version}" \
        SHA_HEAD_SHORT="${sha}" \
        bash "${PATCHED_SCRIPT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# image-info.json generation
# ──────────────────────────────────────────────────────────────────────────────

@test "image-info: image-info.json is created" {
    _run_image_info
    [ "$status" -eq 0 ]
    [ -f "${TEST_ROOT}/usr/share/ublue-os/image-info.json" ]
}

@test "image-info: image-info.json contains image-name" {
    _run_image_info bluefin
    [ "$status" -eq 0 ]
    grep -q '"image-name": "bluefin"' "${TEST_ROOT}/usr/share/ublue-os/image-info.json"
}

@test "image-info: image-info.json contains image-vendor" {
    _run_image_info bluefin projectbluefin
    [ "$status" -eq 0 ]
    grep -q '"image-vendor": "projectbluefin"' "${TEST_ROOT}/usr/share/ublue-os/image-info.json"
}

@test "image-info: image-info.json contains centos-version" {
    _run_image_info bluefin projectbluefin 10
    [ "$status" -eq 0 ]
    grep -q '"centos-version": "10"' "${TEST_ROOT}/usr/share/ublue-os/image-info.json"
}

@test "image-info: image-tag is 'lts'" {
    _run_image_info bluefin projectbluefin 10
    [ "$status" -eq 0 ]
    grep -q '"image-tag": "lts"' "${TEST_ROOT}/usr/share/ublue-os/image-info.json"
}

# ──────────────────────────────────────────────────────────────────────────────
# os-release patching
# ──────────────────────────────────────────────────────────────────────────────

@test "image-info: os-release NAME is set to 'Bluefin LTS'" {
    _run_image_info
    [ "$status" -eq 0 ]
    grep -q 'NAME="Bluefin LTS"' "${TEST_ROOT}/usr/lib/os-release"
}

@test "image-info: os-release PRETTY_NAME is set to 'Bluefin LTS'" {
    _run_image_info
    [ "$status" -eq 0 ]
    grep -q 'PRETTY_NAME="Bluefin LTS"' "${TEST_ROOT}/usr/lib/os-release"
}

@test "image-info: os-release VERSION_CODENAME is set to Achillobator" {
    _run_image_info
    [ "$status" -eq 0 ]
    grep -q 'VERSION_CODENAME="Achillobator"' "${TEST_ROOT}/usr/lib/os-release"
}

@test "image-info: os-release CPE_NAME is rewritten to universal-blue:bluefin-lts" {
    _run_image_info
    [ "$status" -eq 0 ]
    grep -q 'cpe:/o:universal-blue:bluefin-lts' "${TEST_ROOT}/usr/lib/os-release"
}

@test "image-info: os-release strips REDHAT_ fields" {
    _run_image_info
    [ "$status" -eq 0 ]
    run grep "REDHAT_" "${TEST_ROOT}/usr/lib/os-release"
    [ "$status" -ne 0 ]
}

@test "image-info: os-release appends DOCUMENTATION_URL" {
    _run_image_info
    [ "$status" -eq 0 ]
    grep -q 'DOCUMENTATION_URL="https://docs.projectbluefin.io"' "${TEST_ROOT}/usr/lib/os-release"
}

@test "image-info: os-release appends BUILD_ID from SHA_HEAD_SHORT" {
    _run_image_info bluefin projectbluefin 10 abc1234
    [ "$status" -eq 0 ]
    grep -q 'BUILD_ID="abc1234"' "${TEST_ROOT}/usr/lib/os-release"
}

@test "image-info: os-release appends DEFAULT_HOSTNAME=bluefin" {
    _run_image_info
    [ "$status" -eq 0 ]
    grep -q 'DEFAULT_HOSTNAME="bluefin"' "${TEST_ROOT}/usr/lib/os-release"
}

# ──────────────────────────────────────────────────────────────────────────────
# smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "image-info: script exits 0 with env set" {
    _run_image_info
    [ "$status" -eq 0 ]
}
