#!/usr/bin/env bats

# Unit tests for build_scripts/overrides/x86_64/20-zfs.sh
# Run with: bats tests/unit/zfs_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
ZFS_SCRIPT="${SCRIPT_DIR}/../../build_scripts/overrides/x86_64/20-zfs.sh"

patch_and_run() {
    PATCHED_SCRIPT="${TEST_ROOT}/20-zfs-patched.sh"
    sed \
        -e "s|/tmp/akmods-zfs-rpms|${AKMODS_DIR}|g" \
        -e "s|/usr/lib/modules-load.d|${TEST_ROOT}/usr/lib/modules-load.d|g" \
        -e "s|/usr/bin/dracut|${STUB_BIN}/dracut|g" \
        -e "s|/lib/modules/\$QUALIFIED_KERNEL|${TEST_ROOT}/lib/modules/\$QUALIFIED_KERNEL|g" \
        "${ZFS_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"
    run bash "${PATCHED_SCRIPT}"
}

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    AKMODS_DIR="${TEST_ROOT}/akmods-zfs-rpms"
    DNF_LOG="${TEST_ROOT}/dnf.log"
    CMD_LOG="${TEST_ROOT}/cmd.log"

    mkdir -p "${STUB_BIN}" \
        "${TEST_ROOT}/usr/lib/modules-load.d" \
        "${AKMODS_DIR}/kmods/zfs"

    export STUB_KERNEL_LIST="kernel-6.12.0-100.el10.x86_64"
    export STUB_QUALIFIED_KERNEL="6.12.0-100.el10.x86_64"
    export STUB_KERNEL_VRA="6.12.0-100.el10.x86_64"

    # rpm stub: `rpm -qa` for the qualified kernel, `rpm -q kernel` for the EVR.ARCH.
    cat > "${STUB_BIN}/rpm" <<EOF
#!/usr/bin/env bash
echo "rpm \$*" >> "${CMD_LOG}"
if [[ "\$1" == "-qa" ]]; then
    printf '%s\n' \${STUB_KERNEL_LIST}
else
    printf '%s' "\${STUB_KERNEL_VRA}"
fi
exit 0
EOF

    cat > "${STUB_BIN}/dnf" <<EOF
#!/usr/bin/env bash
echo "dnf \$*" >> "${DNF_LOG}"
exit 0
EOF

    for cmd in depmod dracut; do
        cat > "${STUB_BIN}/${cmd}" <<EOF
#!/usr/bin/env bash
echo "${cmd} \$*" >> "${CMD_LOG}"
exit 0
EOF
    done

    chmod +x "${STUB_BIN}"/*
    export PATH="${STUB_BIN}:${PATH}"
    export TEST_ROOT STUB_BIN AKMODS_DIR DNF_LOG CMD_LOG

    # Happy-path fixture: the akmods image layout the build actually mounts.
    : > "${AKMODS_DIR}/kmods/zfs/kmod-zfs-2.2.7.rpm"
    : > "${AKMODS_DIR}/kmods/zfs/zfs-2.2.7.rpm"
    : > "${AKMODS_DIR}/kmods/zfs/python3-pyzfs-2.2.7.rpm"
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Script smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "zfs: exits 0 on the happy path" {
    patch_and_run
    [ "$status" -eq 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# RPM discovery
# ──────────────────────────────────────────────────────────────────────────────

@test "zfs: fails when the akmods image provided no ZFS RPMs" {
    rm -f "${AKMODS_DIR}"/kmods/zfs/*.rpm
    patch_and_run
    [ "$status" -eq 1 ]
    [[ "$output" == *"no ZFS RPMs were provided by the akmods image"* ]]
}

@test "zfs: fails when only python3-pyzfs is present" {
    rm -f "${AKMODS_DIR}"/kmods/zfs/*.rpm
    : > "${AKMODS_DIR}/kmods/zfs/python3-pyzfs-2.2.7.rpm"
    patch_and_run
    [ "$status" -eq 1 ]
    [[ "$output" == *"no ZFS RPMs were provided by the akmods image"* ]]
}

@test "zfs: installs the kmod and userland RPMs" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "kmod-zfs-2.2.7.rpm" "${DNF_LOG}"
    grep -q "zfs-2.2.7.rpm" "${DNF_LOG}"
}

@test "zfs: excludes python3-pyzfs from the main install transaction" {
    patch_and_run
    [ "$status" -eq 0 ]
    ! grep -v -- "--skip-broken" "${DNF_LOG}" | grep -q "python3-pyzfs"
}

@test "zfs: installs python3-pyzfs separately with --skip-broken" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -- "--skip-broken" "${DNF_LOG}" | grep -q "python3-pyzfs"
}

@test "zfs: ignores RPMs nested below the zfs kmods directory" {
    mkdir -p "${AKMODS_DIR}/kmods/zfs/nested"
    : > "${AKMODS_DIR}/kmods/zfs/nested/kmod-zfs-nested.rpm"
    patch_and_run
    [ "$status" -eq 0 ]
    ! grep -q "kmod-zfs-nested.rpm" "${DNF_LOG}"
}

@test "zfs: ignores non-RPM files in the kmods directory" {
    : > "${AKMODS_DIR}/kmods/zfs/README.md"
    patch_and_run
    [ "$status" -eq 0 ]
    ! grep -q "README.md" "${DNF_LOG}"
}

@test "zfs: tolerates a missing python3-pyzfs RPM" {
    rm -f "${AKMODS_DIR}/kmods/zfs/python3-pyzfs-2.2.7.rpm"
    patch_and_run
    [ "$status" -eq 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Module wiring
# ──────────────────────────────────────────────────────────────────────────────

@test "zfs: runs depmod for the installed kernel VRA" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "depmod -a ${STUB_KERNEL_VRA}" "${CMD_LOG}"
}

@test "zfs: autoloads the zfs module via modules-load.d" {
    patch_and_run
    [ "$status" -eq 0 ]
    [ "$(cat "${TEST_ROOT}/usr/lib/modules-load.d/zfs.conf")" = "zfs" ]
}

@test "zfs: rebuilds the initramfs for the qualified kernel" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "dracut .*--kver ${STUB_QUALIFIED_KERNEL}" "${CMD_LOG}"
    grep -q -- "${TEST_ROOT}/lib/modules/${STUB_QUALIFIED_KERNEL}/initramfs.img" "${CMD_LOG}"
}

@test "zfs: builds a reproducible ostree initramfs" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "dracut .*--no-hostonly" "${CMD_LOG}"
    grep -q -- "dracut .*--reproducible" "${CMD_LOG}"
    grep -q -- "dracut .*--add ostree" "${CMD_LOG}"
}

@test "zfs: picks the last matching kernel when several are installed" {
    export STUB_KERNEL_LIST="kernel-6.12.0-100.el10.x86_64 kernel-6.12.1-200.el10.x86_64"
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "dracut .*--kver 6.12.1-200.el10.x86_64" "${CMD_LOG}"
}
