#!/usr/bin/env bats

# Unit tests for build_scripts/scripts/kernel-swap.sh
# Run with: bats tests/unit/kernel_swap_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
KERNEL_SWAP="${SCRIPT_DIR}/../../build_scripts/scripts/kernel-swap.sh"

KERNEL_VER="7.0.8-200.fc44.x86_64"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    DNF_LOG="${TEST_ROOT}/dnf.log"
    DRACUT_LOG="${TEST_ROOT}/dracut.log"
    DEPMOD_LOG="${TEST_ROOT}/depmod.log"
    SKOPEO_LOG="${TEST_ROOT}/skopeo.log"

    mkdir -p "${STUB_BIN}"
    mkdir -p "${TEST_ROOT}/tmp/kernel-rpms"
    mkdir -p "${TEST_ROOT}/etc/dracut.conf.d"
    mkdir -p "${TEST_ROOT}/lib/modules/${KERNEL_VER}"
    mkdir -p "${TEST_ROOT}/etc/pki/akmods/certs"
    mkdir -p "${TEST_ROOT}/run"

    # Fake kernel RPMs for the default fc version
    touch "${TEST_ROOT}/tmp/kernel-rpms/kernel-${KERNEL_VER}.rpm"
    touch "${TEST_ROOT}/tmp/kernel-rpms/kernel-core-${KERNEL_VER}.rpm"
    touch "${TEST_ROOT}/tmp/kernel-rpms/kernel-modules-${KERNEL_VER}.rpm"
    touch "${TEST_ROOT}/tmp/kernel-rpms/kernel-devel-${KERNEL_VER}.rpm"

    export PATH="${STUB_BIN}:${PATH}"
    export DNF_LOG DRACUT_LOG DEPMOD_LOG SKOPEO_LOG TEST_ROOT

    # ── rpm stub ─────────────────────────────────────────────────────────────
    # rpm --erase → exit 0
    # rpm -q kernel --queryformat → echo KERNEL_VER
    # rpm -qa → empty (no akmods installed yet)
    cat > "${STUB_BIN}/rpm" <<EOF
#!/usr/bin/bash
for arg in "\$@"; do
    if [[ "\${arg}" == "--queryformat" ]]; then
        echo "${KERNEL_VER}"
        exit 0
    fi
done
exit 0
EOF
    chmod +x "${STUB_BIN}/rpm"

    # ── dnf stub ─────────────────────────────────────────────────────────────
    cat > "${STUB_BIN}/dnf" <<'EOF'
#!/usr/bin/bash
echo "dnf $*" >> "${DNF_LOG}"
exit 0
EOF
    chmod +x "${STUB_BIN}/dnf"

    # ── depmod stub ──────────────────────────────────────────────────────────
    cat > "${STUB_BIN}/depmod" <<'EOF'
#!/usr/bin/bash
echo "depmod $*" >> "${DEPMOD_LOG}"
exit 0
EOF
    chmod +x "${STUB_BIN}/depmod"

    # ── dracut stub ──────────────────────────────────────────────────────────
    # Creates the initramfs file at the -f <path> argument.
    cat > "${STUB_BIN}/dracut" <<'STUBEOF'
#!/usr/bin/bash
echo "dracut $*" >> "${DRACUT_LOG}"
prev=""
for arg in "$@"; do
    if [[ "${prev}" == "-f" ]]; then
        mkdir -p "$(dirname "${arg}")"
        touch "${arg}"
    fi
    prev="${arg}"
done
exit 0
STUBEOF
    chmod +x "${STUB_BIN}/dracut"

    # ── skopeo stub ──────────────────────────────────────────────────────────
    # Creates a dir: target with a fake manifest.json and payload blob.
    cat > "${STUB_BIN}/skopeo" <<'STUBEOF'
#!/usr/bin/bash
echo "skopeo $*" >> "${SKOPEO_LOG}"
for arg in "$@"; do
    if [[ "${arg}" == dir:* ]]; then
        target="${arg#dir:}"
        mkdir -p "${target}"
        printf '{"layers":[{"digest":"sha256:abc123fake"}]}\n' > "${target}/manifest.json"
        touch "${target}/abc123fake"
    fi
done
exit 0
STUBEOF
    chmod +x "${STUB_BIN}/skopeo"

    # ── jq stub ──────────────────────────────────────────────────────────────
    # Returns a constant digest; cut -d : -f 2 extracts "abc123fake"
    cat > "${STUB_BIN}/jq" <<'EOF'
#!/usr/bin/bash
echo "sha256:abc123fake"
EOF
    chmod +x "${STUB_BIN}/jq"

    # ── tar stub ─────────────────────────────────────────────────────────────
    # Creates rpms/ structure in the -C target dir.
    cat > "${STUB_BIN}/tar" <<'STUBEOF'
#!/usr/bin/bash
target=""
prev=""
for i in "$@"; do
    if [[ "${prev}" == "-C" ]]; then target="${i}"; fi
    prev="${i}"
done
if [[ -n "${target}" ]]; then
    mkdir -p "${target}/rpms/kmods"
    touch "${target}/rpms/xone-kmod-common-1.rpm"
    touch "${target}/rpms/kmods/kmod-xone-1.rpm"
fi
exit 0
STUBEOF
    chmod +x "${STUB_BIN}/tar"

    # ── ghcurl stub ──────────────────────────────────────────────────────────
    # Writes a fake cert to the -Lo <path> destination.
    cat > "${STUB_BIN}/ghcurl" <<'EOF'
#!/usr/bin/bash
lo_next=0
for arg in "$@"; do
    if [[ "${lo_next}" == "1" ]]; then
        mkdir -p "$(dirname "${arg}")"
        printf 'Universal Blue certificate\n' > "${arg}"
        lo_next=0
    fi
    [[ "${arg}" == "-Lo" ]] && lo_next=1
done
exit 0
EOF
    chmod +x "${STUB_BIN}/ghcurl"

    # ── Patch absolute paths into sandbox ────────────────────────────────────
    PATCHED_SCRIPT="${TEST_ROOT}/kernel-swap-patched.sh"
    sed \
        -e "s|/tmp/kernel-rpms|${TEST_ROOT}/tmp/kernel-rpms|g" \
        -e "s|/etc/dracut\.conf\.d|${TEST_ROOT}/etc/dracut.conf.d|g" \
        -e "s|\"/lib/modules/|\"${TEST_ROOT}/lib/modules/|g" \
        -e "s|COMMON_AKMODS_DIR=\"/run/common-akmods\"|COMMON_AKMODS_DIR=\"${TEST_ROOT}/run/common-akmods\"|g" \
        -e "s|/etc/pki/akmods/|${TEST_ROOT}/etc/pki/akmods/|g" \
        "${KERNEL_SWAP}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"
    export PATCHED_SCRIPT
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# ─────────────────────────────────────────────────────────────────────────────
# Happy path — standard fc kernel
# ─────────────────────────────────────────────────────────────────────────────

@test "kernel-swap: exits 0 for standard fc kernel install" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
}

@test "kernel-swap: detects kernel version from RPM filename" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Detected kernel version: ${KERNEL_VER}"* ]]
}

@test "kernel-swap: kernel installed with tsflags=noscripts" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "tsflags=noscripts" "${DNF_LOG}"
}

@test "kernel-swap: depmod called with detected kernel version" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ -f "${DEPMOD_LOG}" ]
    grep -q "${KERNEL_VER}" "${DEPMOD_LOG}"
}

@test "kernel-swap: dracut called with --reproducible flag" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ -f "${DRACUT_LOG}" ]
    grep -q -- "--reproducible" "${DRACUT_LOG}"
}

@test "kernel-swap: dracut called with detected kernel version" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "${KERNEL_VER}" "${DRACUT_LOG}"
}

@test "kernel-swap: versionlock applied to kernel packages" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "versionlock" "${DNF_LOG}"
}

@test "kernel-swap: akmods cert fetched into pki certs dir" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ -f "${TEST_ROOT}/etc/pki/akmods/certs/akmods-ublue.der" ]
}

# ─────────────────────────────────────────────────────────────────────────────
# dracut.conf.d lifecycle
# ─────────────────────────────────────────────────────────────────────────────

@test "kernel-swap: dracut tmpdir config removed after install" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ ! -f "${TEST_ROOT}/etc/dracut.conf.d/01-tmpdir.conf" ]
}

@test "kernel-swap: fc kernel writes microcode-omit dracut config" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ -f "${TEST_ROOT}/etc/dracut.conf.d/02-omit-unsupported-microcode.conf" ]
    grep -q "microcode_ctl" "${TEST_ROOT}/etc/dracut.conf.d/02-omit-unsupported-microcode.conf"
}

@test "kernel-swap: el kernel does NOT write microcode-omit dracut config" {
    EL_VER="7.0.8-200.el10.x86_64"
    rm -f "${TEST_ROOT}/tmp/kernel-rpms/"*.rpm
    touch "${TEST_ROOT}/tmp/kernel-rpms/kernel-${EL_VER}.rpm"

    cat > "${STUB_BIN}/rpm" <<EOF
#!/usr/bin/bash
for arg in "\$@"; do
    if [[ "\${arg}" == "--queryformat" ]]; then
        echo "${EL_VER}"
        exit 0
    fi
done
exit 0
EOF
    chmod +x "${STUB_BIN}/rpm"

    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ ! -f "${TEST_ROOT}/etc/dracut.conf.d/02-omit-unsupported-microcode.conf" ]
}

# ─────────────────────────────────────────────────────────────────────────────
# Error path — missing kernel RPMs
# ─────────────────────────────────────────────────────────────────────────────

@test "kernel-swap: exits non-zero when no kernel RPMs found" {
    rm -f "${TEST_ROOT}/tmp/kernel-rpms/"*.rpm
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -ne 0 ]
    [[ "$output" == *"ERROR: Could not detect kernel version"* ]]
}

# ─────────────────────────────────────────────────────────────────────────────
# HWE common akmods
# ─────────────────────────────────────────────────────────────────────────────

@test "kernel-swap: skopeo called to fetch common akmods" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ -f "${SKOPEO_LOG}" ]
    grep -q "akmods:coreos-stable" "${SKOPEO_LOG}"
}

@test "kernel-swap: common akmods dir cleaned up after install" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ ! -d "${TEST_ROOT}/run/common-akmods" ]
}

@test "kernel-swap: Fedora version derived from installed kernel NVR" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    # fc44 kernel → fedora 44 → skopeo tag contains -44-
    grep -q "\-44\-" "${SKOPEO_LOG}"
}

@test "kernel-swap: FEDORA_AKMODS_VERSION env used as fallback for el kernels" {
    EL_VER="7.0.8-200.el10.x86_64"
    rm -f "${TEST_ROOT}/tmp/kernel-rpms/"*.rpm
    touch "${TEST_ROOT}/tmp/kernel-rpms/kernel-${EL_VER}.rpm"

    cat > "${STUB_BIN}/rpm" <<EOF
#!/usr/bin/bash
for arg in "\$@"; do
    if [[ "\${arg}" == "--queryformat" ]]; then
        echo "${EL_VER}"
        exit 0
    fi
done
exit 0
EOF
    chmod +x "${STUB_BIN}/rpm"

    export FEDORA_AKMODS_VERSION="43"
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "\-43\-" "${SKOPEO_LOG}"
}
