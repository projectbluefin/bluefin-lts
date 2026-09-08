#!/usr/bin/env bats

# Unit tests for build_scripts/overrides/dx/00-packages.sh
# Run with: bats tests/unit/dx_packages_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
DX_SCRIPT="${SCRIPT_DIR}/../../build_scripts/overrides/dx/00-packages.sh"

# The script touches no absolute paths of its own — every side effect goes
# through dnf — so it runs unmodified against a stubbed dnf on PATH.
run_script() {
    run bash "${DX_SCRIPT}"
}

# Line number of the first dnf invocation matching a pattern, for ordering asserts.
dnf_line() {
    grep -n -- "$1" "${DNF_LOG}" | head -1 | cut -d: -f1
}

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    DNF_LOG="${TEST_ROOT}/dnf.log"

    mkdir -p "${STUB_BIN}"

    cat > "${STUB_BIN}/dnf" <<EOF
#!/usr/bin/env bash
echo "dnf \$*" >> "${DNF_LOG}"
exit 0
EOF

    chmod +x "${STUB_BIN}"/*
    export PATH="${STUB_BIN}:${PATH}"
    export TEST_ROOT STUB_BIN DNF_LOG
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Script smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "dx: exits 0 on the happy path" {
    run_script
    [ "$status" -eq 0 ]
}

@test "dx: propagates a dnf failure instead of continuing" {
    cat > "${STUB_BIN}/dnf" <<EOF
#!/usr/bin/env bash
echo "dnf \$*" >> "${DNF_LOG}"
exit 5
EOF
    chmod +x "${STUB_BIN}/dnf"
    run_script
    [ "$status" -eq 5 ]
    # The first dnf call is the VSCode repo add; nothing after it may run.
    [ "$(wc -l < "${DNF_LOG}")" -eq 1 ]
}

@test "dx: every package transaction goes through dnf" {
    run_script
    [ "$status" -eq 0 ]
    [ "$(grep -c "^dnf " "${DNF_LOG}")" -eq "$(wc -l < "${DNF_LOG}")" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# VSCode: third-party repo must not stay enabled
# ──────────────────────────────────────────────────────────────────────────────

@test "dx: adds the Microsoft VSCode repo" {
    run_script
    [ "$status" -eq 0 ]
    grep -q -- "config-manager --add-repo https://packages.microsoft.com/yumrepos/vscode" "${DNF_LOG}"
}

@test "dx: disables the VSCode repo before installing from it" {
    run_script
    [ "$status" -eq 0 ]
    [ "$(dnf_line "--set-disabled packages.microsoft.com_yumrepos_vscode")" \
        -lt "$(dnf_line "--enablerepo packages.microsoft.com_yumrepos_vscode")" ]
}

@test "dx: installs code from the VSCode repo enabled for that transaction only" {
    run_script
    [ "$status" -eq 0 ]
    grep -q -- "--enablerepo packages.microsoft.com_yumrepos_vscode .*install code" "${DNF_LOG}"
}

@test "dx: leaves no dnf call that enables the VSCode repo permanently" {
    run_script
    [ "$status" -eq 0 ]
    ! grep -q -- "--set-enabled packages.microsoft.com_yumrepos_vscode" "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# GPG checking: --nogpgcheck must stay scoped to the VSCode transaction
# ──────────────────────────────────────────────────────────────────────────────

@test "dx: only the VSCode install skips gpg checking" {
    run_script
    [ "$status" -eq 0 ]
    [ "$(grep -c -- "--nogpgcheck" "${DNF_LOG}")" -eq 1 ]
    grep -- "--nogpgcheck" "${DNF_LOG}" | grep -q "install code"
}

@test "dx: the docker transaction verifies signatures" {
    run_script
    [ "$status" -eq 0 ]
    ! grep -- "docker-ce" "${DNF_LOG}" | grep -q -- "--nogpgcheck"
}

# ──────────────────────────────────────────────────────────────────────────────
# Docker CE
# ──────────────────────────────────────────────────────────────────────────────

@test "dx: adds the Docker CE repo for CentOS" {
    run_script
    [ "$status" -eq 0 ]
    grep -q -- "config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo" "${DNF_LOG}"
}

@test "dx: disables docker-ce-stable before installing from it" {
    run_script
    [ "$status" -eq 0 ]
    [ "$(dnf_line "--set-disabled docker-ce-stable")" -lt "$(dnf_line "--enablerepo docker-ce-stable")" ]
}

@test "dx: installs the full Docker CE package set" {
    run_script
    [ "$status" -eq 0 ]
    local line
    line="$(grep -- "--enablerepo docker-ce-stable" "${DNF_LOG}")"
    for pkg in docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin; do
        [[ " ${line} " == *" ${pkg} "* ]]
    done
}

@test "dx: does not permanently enable docker-ce-stable" {
    run_script
    [ "$status" -eq 0 ]
    ! grep -q -- "--set-enabled docker-ce-stable" "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Virtualisation stack
# ──────────────────────────────────────────────────────────────────────────────

@test "dx: installs libvirt from the ublue-os COPR" {
    run_script
    [ "$status" -eq 0 ]
    local line
    line="$(grep -- "copr:copr.fedorainfracloud.org:ublue-os:packages" "${DNF_LOG}")"
    for pkg in libvirt libvirt-daemon-kvm libvirt-nss virt-install ublue-os-libvirt-workarounds; do
        [[ " ${line} " == *" ${pkg} "* ]]
    done
}

# ──────────────────────────────────────────────────────────────────────────────
# Cockpit
# ──────────────────────────────────────────────────────────────────────────────

@test "dx: installs cockpit without weak dependencies" {
    run_script
    [ "$status" -eq 0 ]
    grep -q -- "--setopt=install_weak_deps=False" "${DNF_LOG}"
    grep -- "--setopt=install_weak_deps=False" "${DNF_LOG}" | grep -q "cockpit-bridge"
}

@test "dx: installs the full cockpit module set" {
    run_script
    [ "$status" -eq 0 ]
    local line
    line="$(grep -- "cockpit-bridge" "${DNF_LOG}")"
    for pkg in cockpit-bridge cockpit-machines cockpit-networkmanager cockpit-ostree \
        cockpit-podman cockpit-selinux cockpit-storaged cockpit-system; do
        [[ " ${line} " == *" ${pkg} "* ]]
    done
}

@test "dx: does not pull cockpit-ws into the image" {
    run_script
    [ "$status" -eq 0 ]
    ! grep -q -- " cockpit-ws" "${DNF_LOG}"
}
