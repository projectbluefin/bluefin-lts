#!/usr/bin/env bats

# Unit tests for build_scripts/overrides/dx/00-packages.sh
# Run with: bats tests/unit/dx_packages_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
DX_SCRIPT="${SCRIPT_DIR}/../../build_scripts/overrides/dx/00-packages.sh"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    DNF_LOG="${TEST_ROOT}/dnf.log"

    mkdir -p "${STUB_BIN}"

    # The script only shells out to dnf (config-manager + install). Stub it and
    # log every invocation so assertions read the call sequence from the log.
    cat > "${STUB_BIN}/dnf" <<EOF
#!/usr/bin/env bash
echo "dnf \$*" >> "${DNF_LOG}"
exit 0
EOF
    chmod +x "${STUB_BIN}/dnf"

    export PATH="${STUB_BIN}:${PATH}"
    export DNF_LOG TEST_ROOT STUB_BIN
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

run_script() {
    run bash "${DX_SCRIPT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Script smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "dx-packages: exits 0 with a stubbed dnf" {
    run_script
    [ "$status" -eq 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# VSCode repo — added, disabled, then enabled only for the install
# ──────────────────────────────────────────────────────────────────────────────

@test "dx-packages: adds the Microsoft VSCode repo" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "config-manager --add-repo https://packages.microsoft.com/yumrepos/vscode" "${DNF_LOG}"
}

@test "dx-packages: disables the VSCode repo after adding it" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "config-manager --set-disabled packages.microsoft.com_yumrepos_vscode" "${DNF_LOG}"
}

@test "dx-packages: installs code with --nogpgcheck, repo enabled" {
    run_script
    [ "$status" -eq 0 ]
    grep -q -- "--nogpgcheck install code" "${DNF_LOG}"
    grep -q "enablerepo packages.microsoft.com_yumrepos_vscode" "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Docker CE repo — added, disabled, then enabled only for the install
# ──────────────────────────────────────────────────────────────────────────────

@test "dx-packages: adds the Docker CE repo" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo" "${DNF_LOG}"
}

@test "dx-packages: disables the docker-ce-stable repo after adding it" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "config-manager --set-disabled docker-ce-stable" "${DNF_LOG}"
}

@test "dx-packages: installs docker-ce with the repo enabled" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "enablerepo docker-ce-stable install" "${DNF_LOG}"
    grep -q "docker-ce" "${DNF_LOG}"
    grep -q "docker-compose-plugin" "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# libvirt + cockpit
# ──────────────────────────────────────────────────────────────────────────────

@test "dx-packages: installs libvirt from the ublue-os packages COPR" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "enablerepo copr:copr.fedorainfracloud.org:ublue-os:packages install" "${DNF_LOG}"
    grep -q "libvirt-daemon-kvm" "${DNF_LOG}"
}

@test "dx-packages: installs cockpit with weak deps disabled" {
    run_script
    [ "$status" -eq 0 ]
    grep -q -- "--setopt=install_weak_deps=False install" "${DNF_LOG}"
    grep -q "cockpit-system" "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Ordering — repos are disabled before the packages that enable them run
# ──────────────────────────────────────────────────────────────────────────────

@test "dx-packages: VSCode repo is disabled before code is installed" {
    run_script
    [ "$status" -eq 0 ]
    disable_line=$(grep -n "set-disabled packages.microsoft.com_yumrepos_vscode" "${DNF_LOG}" | head -1 | cut -d: -f1)
    install_line=$(grep -n "install code" "${DNF_LOG}" | head -1 | cut -d: -f1)
    [ -n "$disable_line" ]
    [ -n "$install_line" ]
    [ "$disable_line" -lt "$install_line" ]
}
