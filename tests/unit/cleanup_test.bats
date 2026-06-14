#!/usr/bin/env bats

# Unit tests for build_scripts/cleanup.sh
# Run with: bats tests/unit/cleanup_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
CLEANUP_SCRIPT="${SCRIPT_DIR}/../../build_scripts/cleanup.sh"

setup() {
    TEST_ROOT="${SCRIPT_DIR}/.bats-sandbox/cleanup.${BATS_TEST_NUMBER:-0}.$$"
    STUB_BIN="${TEST_ROOT}/stub-bin"

    mkdir -p "${STUB_BIN}"
    mkdir -p "${TEST_ROOT}/var/somedir"
    mkdir -p "${TEST_ROOT}/boot/somedir"
    mkdir -p "${TEST_ROOT}/usr/share/ublue-os"
    mkdir -p "${TEST_ROOT}/etc/yum.repos.d"

    # Stub commands that require a real system environment
    for cmd in dnf bootc; do
        cat > "${STUB_BIN}/${cmd}" <<'EOF'
#!/usr/bin/bash
exit 0
EOF
        chmod +x "${STUB_BIN}/${cmd}"
    done

    export PATH="${STUB_BIN}:${PATH}"

    # Create image-info.json with wide-open perms so chmod can be tested
    touch "${TEST_ROOT}/usr/share/ublue-os/image-info.json"
    chmod 777 "${TEST_ROOT}/usr/share/ublue-os/image-info.json"

    # Patch absolute paths to use TEST_ROOT
    PATCHED_SCRIPT="${TEST_ROOT}/cleanup-patched.sh"
    sed \
        -e "s|find /var |find ${TEST_ROOT}/var |g" \
        -e "s|find /boot |find ${TEST_ROOT}/boot |g" \
        -e "s|mkdir -p /var /boot|mkdir -p ${TEST_ROOT}/var ${TEST_ROOT}/boot|g" \
        -e "s|ln -s /var/usrlocal /usr/local|ln -s ${TEST_ROOT}/var/usrlocal ${TEST_ROOT}/usr/local|g" \
        -e "s|chmod 644 /usr/share/ublue-os/image-info.json|chmod 644 ${TEST_ROOT}/usr/share/ublue-os/image-info.json|g" \
        -e "s|rm -rf /.gitkeep|rm -rf ${TEST_ROOT}/.gitkeep|g" \
        "${CLEANUP_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"
    export PATCHED_SCRIPT TEST_ROOT STUB_BIN
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# /var and /boot cleanup
# ──────────────────────────────────────────────────────────────────────────────

@test "cleanup: /var contents are deleted and dir is recreated" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    # subdir should be gone
    [ ! -d "${TEST_ROOT}/var/somedir" ]
    # /var itself should still exist
    [ -d "${TEST_ROOT}/var" ]
}

@test "cleanup: /boot contents are deleted and dir is recreated" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ ! -d "${TEST_ROOT}/boot/somedir" ]
    [ -d "${TEST_ROOT}/boot" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# /usr/local symlink
# ──────────────────────────────────────────────────────────────────────────────

@test "cleanup: /usr/local is replaced with symlink to /var/usrlocal" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ -L "${TEST_ROOT}/usr/local" ]
    link_target=$(readlink "${TEST_ROOT}/usr/local")
    [ "${link_target}" = "${TEST_ROOT}/var/usrlocal" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# image-info.json permissions
# ──────────────────────────────────────────────────────────────────────────────

@test "cleanup: image-info.json is set to 644" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    perms=$(stat -c "%a" "${TEST_ROOT}/usr/share/ublue-os/image-info.json")
    [ "${perms}" = "644" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# .gitkeep removal
# ──────────────────────────────────────────────────────────────────────────────

@test "cleanup: .gitkeep is removed" {
    touch "${TEST_ROOT}/.gitkeep"
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ ! -f "${TEST_ROOT}/.gitkeep" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# dnf stubs (smoke — confirms script reaches completion)
# ──────────────────────────────────────────────────────────────────────────────

@test "cleanup: script exits 0 with dnf and bootc stubbed" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
}

@test "cleanup: dnf config-manager --set-disabled is called" {
    # Replace dnf stub with a recorder
    cat > "${STUB_BIN}/dnf" <<'EOF'
#!/usr/bin/bash
echo "dnf $*" >> "${DNF_LOG}"
exit 0
EOF
    chmod +x "${STUB_BIN}/dnf"
    DNF_LOG="${TEST_ROOT}/dnf.log"
    export DNF_LOG
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "config-manager --set-disabled baseos-compose,appstream-compose" "${DNF_LOG}"
}
