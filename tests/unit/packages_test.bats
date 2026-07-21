#!/usr/bin/env bats

# Unit tests for build_scripts/20-packages.sh
# Run with: bats tests/unit/packages_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
PACKAGES_SCRIPT="${SCRIPT_DIR}/../../build_scripts/20-packages.sh"
READ_PACKAGES="${SCRIPT_DIR}/../../build_scripts/scripts/read-packages"
PKGS_TOML="${SCRIPT_DIR}/../../build_scripts/packages/base.toml"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    DNF_LOG="${TEST_ROOT}/dnf.log"

    mkdir -p "${STUB_BIN}"
    mkdir -p "${TEST_ROOT}/usr/bin"
    mkdir -p "${TEST_ROOT}/usr/lib/systemd/system"
    mkdir -p "${TEST_ROOT}/usr/share/doc"

    export MAJOR_VERSION_NUMBER="10"

    # Create minimal image-versions.yaml for uupd version parsing
    cat > "${TEST_ROOT}/image-versions.yaml" <<'EOF'
images:
  uupd: "v0.0.1-test"
EOF

    # dnf stub: log every invocation
    cat > "${STUB_BIN}/dnf" <<EOF
#!/usr/bin/env bash
echo "dnf \$*" >> "${DNF_LOG}"
exit 0
EOF
    chmod +x "${STUB_BIN}/dnf"

    # curl stub: handle both pipe-to-tar and -o file cases
    cat > "${STUB_BIN}/curl" <<EOF
#!/usr/bin/env bash
# If writing to file (-o flag), create an empty placeholder
for i in "\$@"; do
    if [[ "\${PREV:-}" == "-o" ]]; then
        echo "# stub" > "\$i"
    fi
    PREV="\$i"
done
exit 0
EOF
    chmod +x "${STUB_BIN}/curl"

    # tar stub: when called with -C <dir> <file>, create a stub binary
    cat > "${STUB_BIN}/tar" <<EOF
#!/usr/bin/env bash
DEST_DIR=""
PREV=""
for arg in "\$@"; do
    if [[ "\${PREV}" == "-C" ]]; then DEST_DIR="\${arg}"; fi
    PREV="\${arg}"
done
LAST="\${@: -1}"
if [[ -n "\${DEST_DIR}" && "\${LAST}" != "-"* ]]; then
    mkdir -p "\${DEST_DIR}"
    printf '#!/usr/bin/env bash\nexit 0\n' > "\${DEST_DIR}/\${LAST}"
    chmod +x "\${DEST_DIR}/\${LAST}"
fi
exit 0
EOF
    chmod +x "${STUB_BIN}/tar"

    # chmod/install stubs
    for cmd in chmod install; do
        cat > "${STUB_BIN}/${cmd}" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
        chmod +x "${STUB_BIN}/${cmd}"
    done

    export PATH="${STUB_BIN}:${PATH}"
    export DNF_LOG TEST_ROOT STUB_BIN

    # Patch absolute paths
    PATCHED_SCRIPT="${TEST_ROOT}/packages-patched.sh"
    sed \
        -e "s|python3 /run/context/build_scripts/scripts/read-packages|python3 ${READ_PACKAGES}|g" \
        -e "s|/run/context/build_scripts/packages/base.toml|${PKGS_TOML}|g" \
        -e "s|/run/context/image-versions.yaml|${TEST_ROOT}/image-versions.yaml|g" \
        -e "s|-C /usr/bin|-C ${TEST_ROOT}/usr/bin|g" \
        -e "s|/usr/share/doc/just|${TEST_ROOT}/usr/share/doc/just|g" \
        -e "s|/usr/lib/systemd/system/uupd.service|${TEST_ROOT}/usr/lib/systemd/system/uupd.service|g" \
        -e "s|/usr/lib/systemd/system/uupd.timer|${TEST_ROOT}/usr/lib/systemd/system/uupd.timer|g" \
        -e "s|/usr/bin/uupd|${TEST_ROOT}/usr/bin/uupd|g" \
        "${PACKAGES_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"
    export PATCHED_SCRIPT
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Script smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "packages: script exits 0 with stubs" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Package removal
# ──────────────────────────────────────────────────────────────────────────────

@test "packages: calls dnf remove for packages in base.toml [remove] section" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "dnf.*remove" "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Package install
# ──────────────────────────────────────────────────────────────────────────────

@test "packages: calls dnf install for packages in base.toml [install] section" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "dnf.*install" "${DNF_LOG}"
}

@test "packages: passes -x exclusion flags for excluded packages" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q -- "-x gnome-extensions-app" "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Tailscale
# ──────────────────────────────────────────────────────────────────────────────

@test "packages: adds tailscale repo via dnf config-manager" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "tailscale" "${DNF_LOG}"
}

@test "packages: disables tailscale-stable repo after adding" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "set-disabled.*tailscale-stable\|set-disabled tailscale" "${DNF_LOG}"
}

@test "packages: installs tailscale with enablerepo flag" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "enablerepo.*tailscale\|tailscale-stable" "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# uupd installation
# ──────────────────────────────────────────────────────────────────────────────

@test "packages: uupd binary is placed in usr/bin" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ -f "${TEST_ROOT}/usr/bin/uupd" ]
}

@test "packages: uupd.service unit file is downloaded" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ -f "${TEST_ROOT}/usr/lib/systemd/system/uupd.service" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# GCC install
# ──────────────────────────────────────────────────────────────────────────────

@test "packages: installs gcc" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "install.*gcc\|gcc" "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# GNOME versionlock
# ──────────────────────────────────────────────────────────────────────────────

@test "packages: calls dnf versionlock for GNOME packages" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "versionlock" "${DNF_LOG}"
}
