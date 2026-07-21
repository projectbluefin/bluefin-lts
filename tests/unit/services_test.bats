#!/usr/bin/env bats

# Unit tests for build_scripts/40-services.sh
# Run with: bats tests/unit/services_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
SERVICES_SCRIPT="${SCRIPT_DIR}/../../build_scripts/40-services.sh"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    SYSTEMCTL_LOG="${TEST_ROOT}/systemctl.log"
    AUTHSELECT_LOG="${TEST_ROOT}/authselect.log"

    mkdir -p "${STUB_BIN}"
    mkdir -p "${TEST_ROOT}/usr/lib/systemd/system"
    mkdir -p "${TEST_ROOT}/usr/lib/systemd/logind.conf.d"

    # Create the uupd service file that the script modifies with sed
    cat > "${TEST_ROOT}/usr/lib/systemd/system/uupd.service" <<'EOF'
[Unit]
Description=uupd

[Service]
ExecStart=/usr/bin/uupd
EOF

    # Create logind.conf that the script patches with sed
    cat > "${TEST_ROOT}/usr/lib/systemd/logind.conf" <<'EOF'
#HandleLidSwitch=suspend
#HandleLidSwitchDocked=ignore
#HandleLidSwitchExternalPower=ignore
#SleepOperation=suspend
EOF

    # Create systemd-resolved.service that the script patches
    cat > "${TEST_ROOT}/usr/lib/systemd/system/systemd-resolved.service" <<'EOF'
[Service]
PrivateTmp=yes
EOF

    # systemctl stub
    cat > "${STUB_BIN}/systemctl" <<EOF
#!/usr/bin/env bash
echo "systemctl \$*" >> "${SYSTEMCTL_LOG}"
exit 0
EOF
    chmod +x "${STUB_BIN}/systemctl"

    # authselect stub
    cat > "${STUB_BIN}/authselect" <<EOF
#!/usr/bin/env bash
echo "authselect \$*" >> "${AUTHSELECT_LOG}"
exit 0
EOF
    chmod +x "${STUB_BIN}/authselect"

    export PATH="${STUB_BIN}:${PATH}"
    export SYSTEMCTL_LOG AUTHSELECT_LOG TEST_ROOT STUB_BIN

    # Patch absolute paths
    PATCHED_SCRIPT="${TEST_ROOT}/services-patched.sh"
    sed \
        -e "s|/usr/lib/systemd/system/|${TEST_ROOT}/usr/lib/systemd/system/|g" \
        -e "s|/usr/lib/systemd/logind.conf|${TEST_ROOT}/usr/lib/systemd/logind.conf|g" \
        "${SERVICES_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"
    export PATCHED_SCRIPT
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Script smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "services: script exits 0 with stubs" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# uupd service modification
# ──────────────────────────────────────────────────────────────────────────────

@test "services: uupd service ExecStart gains --disable-module-distrobox flag" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "\-\-disable-module-distrobox" \
        "${TEST_ROOT}/usr/lib/systemd/system/uupd.service"
}

# ──────────────────────────────────────────────────────────────────────────────
# logind.conf hibernate-on-lid patches
# ──────────────────────────────────────────────────────────────────────────────

@test "services: HandleLidSwitch set to suspend-then-hibernate" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "HandleLidSwitch=suspend-then-hibernate" \
        "${TEST_ROOT}/usr/lib/systemd/logind.conf"
}

@test "services: HandleLidSwitchDocked set to suspend-then-hibernate" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "HandleLidSwitchDocked=suspend-then-hibernate" \
        "${TEST_ROOT}/usr/lib/systemd/logind.conf"
}

@test "services: HandleLidSwitchExternalPower set to suspend-then-hibernate" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "HandleLidSwitchExternalPower=suspend-then-hibernate" \
        "${TEST_ROOT}/usr/lib/systemd/logind.conf"
}

@test "services: SleepOperation set to suspend-then-hibernate" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "SleepOperation=suspend-then-hibernate" \
        "${TEST_ROOT}/usr/lib/systemd/logind.conf"
}

# ──────────────────────────────────────────────────────────────────────────────
# systemctl enable/disable/mask calls
# ──────────────────────────────────────────────────────────────────────────────

@test "services: enables gdm.service" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "enable gdm.service" "${SYSTEMCTL_LOG}"
}

@test "services: enables firewalld.service" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "enable firewalld.service" "${SYSTEMCTL_LOG}"
}

@test "services: disables rpm-ostree.service" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "disable rpm-ostree.service" "${SYSTEMCTL_LOG}"
}

@test "services: disables sshd.service" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "disable sshd.service" "${SYSTEMCTL_LOG}"
}

@test "services: enables tailscaled.service" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "enable tailscaled.service" "${SYSTEMCTL_LOG}"
}

@test "services: enables uupd.timer" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "enable uupd.timer" "${SYSTEMCTL_LOG}"
}

@test "services: enables systemd-resolved.service" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "enable systemd-resolved.service" "${SYSTEMCTL_LOG}"
}

@test "services: masks bootc-fetch-apply-updates" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "mask.*bootc-fetch-apply-updates" "${SYSTEMCTL_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# authselect features
# ──────────────────────────────────────────────────────────────────────────────

@test "services: enables with-silent-lastlog feature" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "with-silent-lastlog" "${AUTHSELECT_LOG}"
}

@test "services: enables with-fingerprint feature" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "with-fingerprint" "${AUTHSELECT_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# systemd-resolved PrivateTmp fix
# ──────────────────────────────────────────────────────────────────────────────

@test "services: sets PrivateTmp=no in systemd-resolved.service" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "PrivateTmp=no" \
        "${TEST_ROOT}/usr/lib/systemd/system/systemd-resolved.service"
}
