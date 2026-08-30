#!/usr/bin/env bats

# Unit tests for build_scripts/overrides/nvidia/20-nvidia.sh
# Run with: bats tests/unit/nvidia_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
NVIDIA_SCRIPT="${SCRIPT_DIR}/../../build_scripts/overrides/nvidia/20-nvidia.sh"

# Rewrite every absolute path the script touches into the sandbox, then run it.
# Called after the per-test fixture (RPM layout, stub return values) is in place.
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

# Create an RPM fixture. The stub `rpm` reads NAME/requires from sidecar files
# rather than parsing a real RPM header.
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

    # Defaults the rpm stub answers with; individual tests override these.
    export STUB_KERNEL_LIST="kernel-6.12.0-100.el10.x86_64"
    export STUB_QUALIFIED_KERNEL="6.12.0-100.el10.x86_64"
    export STUB_KMOD_VERSION="580.65.06"
    export STUB_DRIVER_VERSION="580.65.06"

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
        # -qp --qf '%{NAME}' <file>   or   -qp --requires <file>
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

    cat > "${STUB_BIN}/dnf" <<EOF
#!/usr/bin/env bash
echo "dnf \$*" >> "${DNF_LOG}"
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

    # Happy-path fixture: one matching kmod RPM plus one ublue-os RPM.
    make_rpm "${AKMODS_DIR}/kmods/kmod-nvidia-580.rpm" \
        "kmod-nvidia" "kernel-uname-r = ${STUB_QUALIFIED_KERNEL}"
    make_rpm "${AKMODS_DIR}/ublue-os/ublue-os-nvidia-addons.rpm" \
        "ublue-os-nvidia-addons"
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Script smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "nvidia: exits 0 on the happy path" {
    patch_and_run
    [ "$status" -eq 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# kmod RPM selection
# ──────────────────────────────────────────────────────────────────────────────

@test "nvidia: fails when no kmod RPM matches the qualified kernel" {
    rm -f "${AKMODS_DIR}"/kmods/kmod-nvidia-580.rpm*
    make_rpm "${AKMODS_DIR}/kmods/kmod-nvidia-580.rpm" \
        "kmod-nvidia" "kernel-uname-r = 9.9.9-1.el10.x86_64"
    patch_and_run
    [ "$status" -eq 1 ]
    [[ "$output" == *"no NVIDIA kmod RPMs match kernel ${STUB_QUALIFIED_KERNEL}"* ]]
}

@test "nvidia: fails when the kmods directory is empty" {
    rm -rf "${AKMODS_DIR}/kmods"
    mkdir -p "${AKMODS_DIR}/kmods"
    patch_and_run
    [ "$status" -eq 1 ]
    [[ "$output" == *"no NVIDIA kmod RPMs match kernel"* ]]
}

@test "nvidia: skips kmod RPMs built against a different kernel" {
    make_rpm "${AKMODS_DIR}/kmods/kmod-nvidia-stale.rpm" \
        "kmod-nvidia" "kernel-uname-r = 6.11.0-1.el10.x86_64"
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "kmod-nvidia-580.rpm" "${DNF_LOG}"
    ! grep -q "kmod-nvidia-stale.rpm" "${DNF_LOG}"
}

@test "nvidia: keeps non-kmod RPMs regardless of their kernel requires" {
    make_rpm "${AKMODS_DIR}/kmods/nvidia-kmod-common.rpm" \
        "nvidia-kmod-common" "kernel-uname-r = 9.9.9-1.el10.x86_64"
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "nvidia-kmod-common.rpm" "${DNF_LOG}"
}

@test "nvidia: installs kmod RPMs found in nested kmods subdirectories" {
    make_rpm "${AKMODS_DIR}/kmods/nested/kmod-nvidia-extra.rpm" \
        "kmod-nvidia-extra" "kernel-uname-r = ${STUB_QUALIFIED_KERNEL}"
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "nested/kmod-nvidia-extra.rpm" "${DNF_LOG}"
}

@test "nvidia: installs ublue-os RPMs alongside the kmods" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "ublue-os-nvidia-addons.rpm" "${DNF_LOG}"
}

@test "nvidia: ignores ublue-os RPMs nested below maxdepth 1" {
    make_rpm "${AKMODS_DIR}/ublue-os/deeper/ublue-os-ignored.rpm" "ublue-os-ignored"
    patch_and_run
    [ "$status" -eq 0 ]
    ! grep -q "ublue-os-ignored.rpm" "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Repo definition / Fedora version detection
# ──────────────────────────────────────────────────────────────────────────────

@test "nvidia: defaults the negativo17 repo to fedora-43 when no .fc NVR is present" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "repos/nvidia/fedora-43/" "${DNF_LOG}"
}

@test "nvidia: honours FEDORA_AKMODS_VERSION when no .fc NVR is present" {
    export FEDORA_AKMODS_VERSION=41
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "repos/nvidia/fedora-41/" "${DNF_LOG}"
}

@test "nvidia: derives the Fedora version from an .fc NVR in the akmods RPMs" {
    export FEDORA_AKMODS_VERSION=41
    make_rpm "${AKMODS_DIR}/kmods/kmod-nvidia-580.fc44.rpm" \
        "kmod-nvidia" "kernel-uname-r = ${STUB_QUALIFIED_KERNEL}"
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "repos/nvidia/fedora-44/" "${DNF_LOG}"
    ! grep -q "repos/nvidia/fedora-41/" "${DNF_LOG}"
}

@test "nvidia: repo definition pins gpgcheck and the slaanesh key" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "--setopt=fedora-nvidia-lts-install.gpgcheck=1" "${DNF_LOG}"
    grep -q -- "RPM-GPG-KEY-slaanesh" "${DNF_LOG}"
}

@test "nvidia: uses repofrompath rather than dropping a .repo file" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "--repofrompath=fedora-nvidia-lts-install," "${DNF_LOG}"
    grep -q -- "--repofrompath=fedora-nvidia-lts-driver," "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Driver package pinning
# ──────────────────────────────────────────────────────────────────────────────

@test "nvidia: pins driver packages to epoch 3 and the kmod version" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "nvidia-driver-3:${STUB_KMOD_VERSION}" "${DNF_LOG}"
    grep -q "libnvidia-fbc-3:${STUB_KMOD_VERSION}" "${DNF_LOG}"
    grep -q "nvidia-driver-cuda-3:${STUB_KMOD_VERSION}" "${DNF_LOG}"
    grep -q "nvidia-settings-3:${STUB_KMOD_VERSION}" "${DNF_LOG}"
}

@test "nvidia: fails when kmod-nvidia and nvidia-driver versions diverge" {
    export STUB_DRIVER_VERSION="575.00.00"
    patch_and_run
    [ "$status" -eq 1 ]
    [[ "$output" == *"does not match nvidia-driver version"* ]]
}

@test "nvidia: enables the container toolkit repo then disables it again" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "config-manager --set-enabled nvidia-container-toolkit" "${DNF_LOG}"
    grep -q "config-manager --set-disabled nvidia-container-toolkit" "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Image artefacts
# ──────────────────────────────────────────────────────────────────────────────

@test "nvidia: blacklists nouveau in /usr/lib/modprobe.d" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "^blacklist nouveau$" "${TEST_ROOT}/usr/lib/modprobe.d/00-nouveau-blacklist.conf"
    grep -q "^options nouveau modeset=0$" "${TEST_ROOT}/usr/lib/modprobe.d/00-nouveau-blacklist.conf"
}

@test "nvidia: writes bootc kargs that blacklist nouveau and enable drm modeset" {
    patch_and_run
    [ "$status" -eq 0 ]
    local kargs="${TEST_ROOT}/usr/lib/bootc/kargs.d/00-nvidia.toml"
    grep -q "rd.driver.blacklist=nouveau" "${kargs}"
    grep -q "modprobe.blacklist=nouveau" "${kargs}"
    grep -q "nvidia-drm.modeset=1" "${kargs}"
}

@test "nvidia: rewrites the dracut config from omit_drivers to force_drivers" {
    patch_and_run
    [ "$status" -eq 0 ]
    local conf="${TEST_ROOT}/usr/lib/dracut/dracut.conf.d/99-nvidia.conf"
    grep -q "force_drivers" "${conf}"
    ! grep -q "omit_drivers" "${conf}"
}

@test "nvidia: adds i915 and amdgpu to the forced driver list" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q " i915 amdgpu nvidia " "${TEST_ROOT}/usr/lib/dracut/dracut.conf.d/99-nvidia.conf"
}

@test "nvidia: leaves no dracut .tmp file behind" {
    patch_and_run
    [ "$status" -eq 0 ]
    [ ! -e "${TEST_ROOT}/usr/lib/dracut/dracut.conf.d/99-nvidia.conf.tmp" ]
}

@test "nvidia: copies nvidia-modeset.conf into /usr/lib when it exists" {
    echo "options nvidia-drm modeset=1" > "${TEST_ROOT}/etc/modprobe.d/nvidia-modeset.conf"
    patch_and_run
    [ "$status" -eq 0 ]
    [ -f "${TEST_ROOT}/usr/lib/modprobe.d/nvidia-modeset.conf" ]
}

@test "nvidia: tolerates a missing nvidia-modeset.conf (aarch64/SBSA)" {
    patch_and_run
    [ "$status" -eq 0 ]
    [ ! -e "${TEST_ROOT}/usr/lib/modprobe.d/nvidia-modeset.conf" ]
}

@test "nvidia: rebuilds the initramfs for the qualified kernel" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "dracut .*--kver ${STUB_QUALIFIED_KERNEL}" "${CMD_LOG}"
    grep -q -- "${TEST_ROOT}/lib/modules/${STUB_QUALIFIED_KERNEL}/initramfs.img" "${CMD_LOG}"
}

@test "nvidia: builds a reproducible ostree initramfs" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "dracut .*--no-hostonly" "${CMD_LOG}"
    grep -q -- "dracut .*--reproducible" "${CMD_LOG}"
    grep -q -- "dracut .*--add ostree" "${CMD_LOG}"
}

@test "nvidia: enables ublue-nvctk-cdi.service and installs the SELinux module" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "systemctl enable ublue-nvctk-cdi.service" "${CMD_LOG}"
    grep -q "semodule .*nvidia-container.pp" "${CMD_LOG}"
}

@test "nvidia: patches the container runtime config for rootless (no-cgroups) use" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "nvidia-ctk config --set nvidia-container-cli.no-cgroups --in-place" "${CMD_LOG}"
}
