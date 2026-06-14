#!/usr/bin/env bats

# Unit tests for build_scripts/90-image-info.sh
# Run with: bats tests/unit/image_info_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
IMAGE_INFO_SCRIPT="${SCRIPT_DIR}/../../build_scripts/90-image-info.sh"

setup() {
    TEST_ROOT="${SCRIPT_DIR}/.bats-sandbox/image-info.${BATS_TEST_NUMBER:-0}.$$"
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

    export PATH="${STUB_BIN}:${PATH}"

    # Stub external commands used for badges/counts
    for cmd in ghcurl jq numfmt; do
        cat > "${STUB_BIN}/${cmd}" <<'EOF'
#!/usr/bin/bash
echo "0"
EOF
        chmod +x "${STUB_BIN}/${cmd}"
    done

    # curl stub for flathub API
    cat > "${STUB_BIN}/curl" <<'EOF'
#!/usr/bin/bash
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
    export PATCHED_SCRIPT TEST_ROOT STUB_BIN
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

run_script() {
    IMAGE_NAME="${1:-bluefin}"
    IMAGE_VENDOR="${2:-projectbluefin}"
    MAJOR_VERSION_NUMBER="${3:-10}"
    ENABLE_HWE="${4:-0}"
    SHA_HEAD_SHORT="${5:-deadbeef}"
    IMAGE_NAME="${IMAGE_NAME}" \
        IMAGE_VENDOR="${IMAGE_VENDOR}" \
        MAJOR_VERSION_NUMBER="${MAJOR_VERSION_NUMBER}" \
        ENABLE_HWE="${ENABLE_HWE}" \
        SHA_HEAD_SHORT="${SHA_HEAD_SHORT}" \
        bash "${PATCHED_SCRIPT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# image-info.json generation
# ──────────────────────────────────────────────────────────────────────────────

@test "image-info: image-info.json is created" {
    run run_script
    [ "$status" -eq 0 ]
    [ -f "${TEST_ROOT}/usr/share/ublue-os/image-info.json" ]
}

@test "image-info: image-info.json contains image-name" {
    run run_script bluefin
    [ "$status" -eq 0 ]
    grep -q '"image-name": "bluefin"' "${TEST_ROOT}/usr/share/ublue-os/image-info.json"
}

@test "image-info: image-info.json contains image-vendor" {
    run run_script bluefin projectbluefin
    [ "$status" -eq 0 ]
    grep -q '"image-vendor": "projectbluefin"' "${TEST_ROOT}/usr/share/ublue-os/image-info.json"
}

@test "image-info: image-info.json contains centos-version" {
    run run_script bluefin projectbluefin 10
    [ "$status" -eq 0 ]
    grep -q '"centos-version": "10"' "${TEST_ROOT}/usr/share/ublue-os/image-info.json"
}

@test "image-info: image-tag is 'lts' when ENABLE_HWE=0" {
    run run_script bluefin projectbluefin 10 0
    [ "$status" -eq 0 ]
    grep -q '"image-tag": "lts"' "${TEST_ROOT}/usr/share/ublue-os/image-info.json"
}

@test "image-info: image-tag is 'lts-hwe' when ENABLE_HWE=1" {
    run run_script bluefin projectbluefin 10 1
    [ "$status" -eq 0 ]
    grep -q '"image-tag": "lts-hwe"' "${TEST_ROOT}/usr/share/ublue-os/image-info.json"
}

# ──────────────────────────────────────────────────────────────────────────────
# os-release patching
# ──────────────────────────────────────────────────────────────────────────────

@test "image-info: os-release NAME is set to 'Bluefin LTS'" {
    run run_script
    [ "$status" -eq 0 ]
    grep -q 'NAME="Bluefin LTS"' "${TEST_ROOT}/usr/lib/os-release"
}

@test "image-info: os-release PRETTY_NAME is set to 'Bluefin LTS'" {
    run run_script
    [ "$status" -eq 0 ]
    grep -q 'PRETTY_NAME="Bluefin LTS"' "${TEST_ROOT}/usr/lib/os-release"
}

@test "image-info: os-release VERSION_CODENAME is set to Achillobator" {
    run run_script
    [ "$status" -eq 0 ]
    grep -q 'VERSION_CODENAME="Achillobator"' "${TEST_ROOT}/usr/lib/os-release"
}

@test "image-info: os-release CPE_NAME is rewritten to universal-blue:bluefin-lts" {
    run run_script
    [ "$status" -eq 0 ]
    grep -q 'cpe:/o:universal-blue:bluefin-lts' "${TEST_ROOT}/usr/lib/os-release"
}

@test "image-info: os-release strips REDHAT_ fields" {
    run run_script
    [ "$status" -eq 0 ]
    run grep "REDHAT_" "${TEST_ROOT}/usr/lib/os-release"
    [ "$status" -ne 0 ]
}

@test "image-info: os-release appends DOCUMENTATION_URL" {
    run run_script
    [ "$status" -eq 0 ]
    grep -q 'DOCUMENTATION_URL="https://docs.projectbluefin.io"' "${TEST_ROOT}/usr/lib/os-release"
}

@test "image-info: os-release appends BUILD_ID from SHA_HEAD_SHORT" {
    run run_script bluefin projectbluefin 10 0 abc1234
    [ "$status" -eq 0 ]
    grep -q 'BUILD_ID="abc1234"' "${TEST_ROOT}/usr/lib/os-release"
}

@test "image-info: os-release appends DEFAULT_HOSTNAME=bluefin" {
    run run_script
    [ "$status" -eq 0 ]
    grep -q 'DEFAULT_HOSTNAME="bluefin"' "${TEST_ROOT}/usr/lib/os-release"
}

# ──────────────────────────────────────────────────────────────────────────────
# smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "image-info: script exits 0 with env set" {
    run run_script
    [ "$status" -eq 0 ]
}
