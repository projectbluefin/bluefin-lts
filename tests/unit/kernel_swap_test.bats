#!/usr/bin/env bats

# Unit tests for build_scripts/scripts/kernel-swap.sh
# Run with: bats tests/unit/kernel_swap_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
KERNEL_SWAP_SCRIPT="${SCRIPT_DIR}/../../build_scripts/scripts/kernel-swap.sh"

KVER="7.1.8-200.fc44.x86_64"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    CALL_LOG="${TEST_ROOT}/calls.log"

    mkdir -p "${STUB_BIN}" \
        "${TEST_ROOT}/tmp/kernel-rpms" \
        "${TEST_ROOT}/etc/dracut.conf.d" \
        "${TEST_ROOT}/usr/lib/modules/${KVER}" \
        "${TEST_ROOT}/usr/bin" \
        "${TEST_ROOT}/usr/sbin"
    : > "${CALL_LOG}"

    # kmod binary the modprobe links resolve to
    touch "${TEST_ROOT}/usr/bin/kmod"

    export PATH="${STUB_BIN}:${PATH}"
    unset CI

    # Kernel RPMs the script expects to find
    for pkg in kernel kernel-core kernel-modules kernel-modules-core kernel-modules-extra kernel-uki-virt kernel-devel kernel-devel-matched; do
        touch "${TEST_ROOT}/tmp/kernel-rpms/${pkg}-${KVER}.rpm"
    done

    # Default kernel config: Fedora >= 7.1 layout (modprobe under /usr/bin)
    write_kernel_config "${TEST_ROOT}/usr/bin/modprobe"

    # Stubs — record the call, do nothing (or the minimum the script needs)
    for cmd in dnf depmod ghcurl; do
        cat > "${STUB_BIN}/${cmd}" <<EOF
#!/usr/bin/env bash
echo "${cmd} \$*" >> "${CALL_LOG}"
EOF
        chmod +x "${STUB_BIN}/${cmd}"
    done

    cat > "${STUB_BIN}/rpm" <<EOF
#!/usr/bin/env bash
echo "rpm \$*" >> "${CALL_LOG}"
case "\$*" in
    -q\ kernel*) echo "${KVER}" ;;
esac
EOF
    chmod +x "${STUB_BIN}/rpm"

    # dracut snapshots the state of the kernel's modprobe path at call time,
    # so a test can assert the link existed before the initramfs was built.
    cat > "${STUB_BIN}/dracut" <<EOF
#!/usr/bin/env bash
echo "dracut \$*" >> "${CALL_LOG}"
if [[ -L "${TEST_ROOT}/usr/bin/modprobe" ]]; then
    echo "dracut-saw-link \$(readlink "${TEST_ROOT}/usr/bin/modprobe")" >> "${CALL_LOG}"
else
    echo "dracut-saw-no-link" >> "${CALL_LOG}"
fi
EOF
    chmod +x "${STUB_BIN}/dracut"

    # skopeo produces a dir: layout with one empty tar layer; jq reads its digest
    cat > "${STUB_BIN}/skopeo" <<EOF
#!/usr/bin/env bash
echo "skopeo \$*" >> "${CALL_LOG}"
dest="\${@: -1}"; dest="\${dest#dir:}"
mkdir -p "\${dest}"
tar -czf "\${dest}/deadbeef" -T /dev/null
echo '{"layers":[{"digest":"sha256:deadbeef"}]}' > "\${dest}/manifest.json"
EOF
    chmod +x "${STUB_BIN}/skopeo"

    cat > "${STUB_BIN}/jq" <<EOF
#!/usr/bin/env bash
echo "sha256:deadbeef"
EOF
    chmod +x "${STUB_BIN}/jq"

    # Redirect absolute paths into the sandbox
    PATCHED_SCRIPT="${TEST_ROOT}/kernel-swap-patched.sh"
    sed \
        -e "s|/tmp/kernel-rpms|${TEST_ROOT}/tmp/kernel-rpms|g" \
        -e "s|/etc/|${TEST_ROOT}/etc/|g" \
        -e "s|/usr/lib/modules|${TEST_ROOT}/usr/lib/modules|g" \
        -e "s|\"/lib/modules|\"${TEST_ROOT}/lib/modules|g" \
        -e "s|/run/common-akmods|${TEST_ROOT}/run/common-akmods|g" \
        "${KERNEL_SWAP_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"

    export PATCHED_SCRIPT TEST_ROOT STUB_BIN CALL_LOG
}

write_kernel_config() {
    cat > "${TEST_ROOT}/usr/lib/modules/${KVER}/config" <<EOF
CONFIG_MODULE_SIG=y
CONFIG_MODPROBE_PATH="$1"
CONFIG_DM_CRYPT=m
EOF
}

@test "kernel-swap: creates the modprobe path the kernel expects when userspace lacks it" {
    # CentOS Stream 10 layout: only /usr/sbin/modprobe exists
    ln -s ../bin/kmod "${TEST_ROOT}/usr/sbin/modprobe"

    run "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]

    [ -L "${TEST_ROOT}/usr/bin/modprobe" ]
    [ "$(readlink "${TEST_ROOT}/usr/bin/modprobe")" = "/usr/bin/kmod" ]
    [[ "$output" == *"Kernel expects modprobe at ${TEST_ROOT}/usr/bin/modprobe"* ]]
}

@test "kernel-swap: modprobe link exists before dracut builds the initramfs" {
    run "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]

    grep -q "^dracut-saw-link /usr/bin/kmod$" "${CALL_LOG}"
    ! grep -q "^dracut-saw-no-link$" "${CALL_LOG}"
}

@test "kernel-swap: leaves an existing modprobe at the kernel's path untouched" {
    # Fedora-style userspace already provides /usr/bin/modprobe
    ln -s kmod "${TEST_ROOT}/usr/bin/modprobe"

    run "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]

    [ "$(readlink "${TEST_ROOT}/usr/bin/modprobe")" = "kmod" ]
    [[ "$output" != *"Kernel expects modprobe at"* ]]
}

@test "kernel-swap: does nothing when the kernel already points at /usr/sbin/modprobe" {
    # Pre-7.1 Fedora kernels (e.g. 7.0.12-201.fc44) use the CentOS layout
    write_kernel_config "${TEST_ROOT}/usr/sbin/modprobe"
    ln -s ../bin/kmod "${TEST_ROOT}/usr/sbin/modprobe"

    run "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]

    [ ! -e "${TEST_ROOT}/usr/bin/modprobe" ]
    [ "$(readlink "${TEST_ROOT}/usr/sbin/modprobe")" = "../bin/kmod" ]
    [[ "$output" != *"Kernel expects modprobe at"* ]]
}

@test "kernel-swap: does nothing when the kernel config has no CONFIG_MODPROBE_PATH" {
    cat > "${TEST_ROOT}/usr/lib/modules/${KVER}/config" <<EOF
CONFIG_MODULE_SIG=y
EOF

    run "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]

    [ ! -e "${TEST_ROOT}/usr/bin/modprobe" ]
    [[ "$output" != *"Kernel expects modprobe at"* ]]
}

@test "kernel-swap: invokes dracut with reproducible and ostree flags" {
    run "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]

    grep -q "dracut.*--reproducible.*--add ostree" "${CALL_LOG}"
}

@test "kernel-swap: omits microcode_ctl for Fedora kernels" {
    run "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]

    [ -f "${TEST_ROOT}/etc/dracut.conf.d/02-omit-unsupported-microcode.conf" ]
    grep -q 'omit_dracutmodules+=" microcode_ctl' "${TEST_ROOT}/etc/dracut.conf.d/02-omit-unsupported-microcode.conf"
}
