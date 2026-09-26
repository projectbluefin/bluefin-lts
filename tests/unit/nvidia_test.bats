#!/usr/bin/env bats

# Unit tests for build_scripts/overrides/nvidia/20-nvidia.sh
# Run with: bats tests/unit/nvidia_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
NVIDIA_SCRIPT="${SCRIPT_DIR}/../../build_scripts/overrides/nvidia/20-nvidia.sh"

# Rewrite every absolute path the script touches into the sandbox, then run it.
patch_and_run() {
    PATCHED_SCRIPT="${TEST_ROOT}/20-nvidia-patched.sh"
    sed \
        -e "s|/tmp/akmods-nvidia-open-rpms|${AKMODS_DIR}|g" \
        -e "s|/usr/lib/modprobe.d|${TEST_ROOT}/usr/lib/modprobe.d|g" \
        -e "s|/usr/lib/bootc/kargs.d|${TEST_ROOT}/usr/lib/bootc/kargs.d|g" \
        -e "s|/usr/share/selinux|${TEST_ROOT}/usr/share/selinux|g" \
        -e "s|/etc/modprobe.d|${TEST_ROOT}/etc/modprobe.d|g" \
        -e "s|/usr/lib/dracut/dracut.conf.d|${TEST_ROOT}/usr/lib/dracut/dracut.conf.d|g" \
        -e "s|/usr/bin/dracut|${STUB_BIN}/dracut|g" \
        -e "s|/lib/modules/\$QUALIFIED_KERNEL|${TEST_ROOT}/lib/modules/\$QUALIFIED_KERNEL|g" \
        "${NVIDIA_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"
    run bash "${PATCHED_SCRIPT}"
}

# Create an RPM fixture. The stub `rpm` reads NAME/requires from sidecar files.
make_rpm() {
    local path="$1" name="$2" requires="${3:-}"
    mkdir -p "$(dirname "${path}")"
    : > "${path}"
    printf '%s\n' "${name}" > "${path}.name"
    printf '%s\n' "${requires}" > "${path}.requires"
}

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    AKMODS_DIR="${TEST_ROOT}/akmods-nvidia-open-rpms"
    DNF_LOG="${TEST_ROOT}/dnf.log"
    CMD_LOG="${TEST_ROOT}/cmd.log"

    mkdir -p "${STUB_BIN}" \
        "${TEST_ROOT}/usr/lib/modprobe.d" \
        "${TEST_ROOT}/usr/lib/bootc/kargs.d" \
        "${TEST_ROOT}/usr/lib/dracut/dracut.conf.d" \
        "${TEST_ROOT}/usr/share/selinux/packages" \
        "${TEST_ROOT}/etc/modprobe.d" \
        "${AKMODS_DIR}/kmods" \
        "${AKMODS_DIR}/ublue-os"

    # Defaults the stubs answer with; individual tests override these.
    export STUB_KERNEL_LIST="kernel-6.12.0-100.el10.x86_64"
    export STUB_QUALIFIED_KERNEL="6.12.0-100.el10.x86_64"
    export STUB_KMOD_VERSION="610.57.04"
    export STUB_DRIVER_VERSION="610.57.04"

    : > "${TEST_ROOT}/usr/share/selinux/packages/nvidia-container.pp"
    cat > "${TEST_ROOT}/usr/lib/dracut/dracut.conf.d/99-nvidia.conf" <<'EOF'
omit_drivers+=" nvidia nvidia-modeset "
EOF

    # rpm stub: dispatches on the query flags the script actually uses.
    cat > "${STUB_BIN}/rpm" <<EOF
#!/usr/bin/env bash
echo "rpm \$*" >> "${CMD_LOG}"
case "\$1" in
    -qa)
        printf '%s\n' \${STUB_KERNEL_LIST}
        ;;
    -qp)
        target="\${@: -1}"
        if [[ "\$2" == "--requires" ]]; then
            cat "\${target}.requires" 2>/dev/null
        else
            printf '%s' "\$(cat "\${target}.name" 2>/dev/null)"
        fi
        ;;
    -q)
        case "\${@: -1}" in
            kmod-nvidia)   printf '%s' "\${STUB_KMOD_VERSION}" ;;
            nvidia-driver) printf '%s' "\${STUB_DRIVER_VERSION}" ;;
            *)             printf '%s' "0" ;;
        esac
        ;;
esac
exit 0
EOF

    # dnf stub: log every call. When NVIDIA_TEST_ROTATE_DRIVER is set, the
    # first (pinned) driver install fails to emulate negativo17 having dropped
    # the exact kmod version, so the script's --best fallback runs instead.
    cat > "${STUB_BIN}/dnf" <<EOF
#!/usr/bin/env bash
echo "dnf \$*" >> "${DNF_LOG}"
if [[ -n "\${NVIDIA_TEST_ROTATE_DRIVER:-}" ]]; then
    case "\$*" in
        *nvidia-driver-3:\${STUB_KMOD_VERSION}*) exit 1 ;;
    esac
fi
exit 0
EOF

    for cmd in systemctl semodule nvidia-ctk dracut; do
        cat > "${STUB_BIN}/${cmd}" <<EOF
#!/usr/bin/env bash
echo "${cmd} \$*" >> "${CMD_LOG}"
exit 0
EOF
    done

    chmod +x "${STUB_BIN}"/*
    export PATH="${STUB_BIN}:${PATH}"
    export TEST_ROOT STUB_BIN AKMODS_DIR DNF_LOG CMD_LOG

    make_rpm "${AKMODS_DIR}/kmods/kmod-nvidia-610.rpm" \
        "kmod-nvidia" "kernel-uname-r = ${STUB_QUALIFIED_KERNEL}"
    make_rpm "${AKMODS_DIR}/ublue-os/ublue-os-nvidia-addons.rpm" \
        "ublue-os-nvidia-addons"
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Driver package install
# ──────────────────────────────────────────────────────────────────────────────

@test "nvidia: installs the pinned driver when the kmod version is published" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "nvidia-driver-3:${STUB_KMOD_VERSION}" "${DNF_LOG}"
    # the happy path used the exact kmod pin; no --best fallback was needed
    ! grep -q -- "--best --allowerasing" "${DNF_LOG}"
}

@test "nvidia: falls back to the repo's current driver when the pinned one is gone" {
    export NVIDIA_TEST_ROTATE_DRIVER=1
    patch_and_run
    [ "$status" -eq 0 ]
    # the exact pinned install was attempted and failed...
    grep -q "nvidia-driver-3:${STUB_KMOD_VERSION}" "${DNF_LOG}"
    # ...then the --best fallback installed the unpinned current driver.
    grep -q -- "--best --allowerasing" "${DNF_LOG}"
    grep -q "dnf .*--best --allowerasing .*nvidia-driver " "${DNF_LOG}"
}

@test "nvidia: still fails loudly when the installed driver cannot match the kmod" {
    export STUB_DRIVER_VERSION="575.00.00"
    patch_and_run
    [ "$status" -eq 1 ]
    [[ "$output" == *"does not match nvidia-driver version"* ]]
}

@test "nvidia: keeps the container toolkit repo enabled then disabled again" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "config-manager --set-enabled nvidia-container-toolkit" "${DNF_LOG}"
    grep -q "config-manager --set-disabled nvidia-container-toolkit" "${DNF_LOG}"
}
