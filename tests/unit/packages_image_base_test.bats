#!/usr/bin/env bats

# Unit tests for build_scripts/overrides/base/10-packages-image-base.sh
# Run with: bats tests/unit/packages_image_base_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
BASE_SCRIPT="${SCRIPT_DIR}/../../build_scripts/overrides/base/10-packages-image-base.sh"
READ_PACKAGES="${SCRIPT_DIR}/../../build_scripts/scripts/read-packages"
PKGS_TOML="${SCRIPT_DIR}/../../build_scripts/packages/base.toml"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    DNF_LOG="${TEST_ROOT}/dnf.log"

    mkdir -p "${STUB_BIN}"
    mkdir -p "${TEST_ROOT}/etc/yum.repos.d"
    mkdir -p "${TEST_ROOT}/usr/bin"
    mkdir -p "${TEST_ROOT}/tmp"

    export MAJOR_VERSION_NUMBER="10"

    # dnf stub: config-manager, versionlock, install, upgrade, group are all
    # dnf sub-commands, so one stub that logs covers them.
    cat > "${STUB_BIN}/dnf" <<EOF
#!/usr/bin/env bash
echo "dnf \$*" >> "${DNF_LOG}"
exit 0
EOF
    chmod +x "${STUB_BIN}/dnf"

    cat > "${STUB_BIN}/rpm" <<EOF
#!/usr/bin/env bash
echo "rpm \$*" >> "${DNF_LOG}"
exit 0
EOF
    chmod +x "${STUB_BIN}/rpm"

    # kernel-swap.sh is called by absolute path; stub it so this test only
    # covers this script's version-lock logic, not kernel-swap.sh's behavior.
    cat > "${STUB_BIN}/kernel-swap" <<EOF
#!/usr/bin/env bash
echo "kernel-swap \$*" >> "${DNF_LOG}"
exit 0
EOF
    chmod +x "${STUB_BIN}/kernel-swap"

    export PATH="${STUB_BIN}:${PATH}"
    export DNF_LOG TEST_ROOT STUB_BIN

    # dnf config-manager is stubbed, so it never creates the repo file. Stage it
    # so the "repo is found before exclude=libjxl* is appended" path runs.
    printf '[jreilly1821-c10s-gnome-50]\nname=GNOME 50 COPR (EPEL)\nenabled=1\n' \
        > "${TEST_ROOT}/etc/yum.repos.d/jreilly1821-c10s-gnome-50.repo"

    PATCHED_SCRIPT="${TEST_ROOT}/10-packages-image-base-patched.sh"
    # The script only touches four absolute path groups; target each exactly so
    # the /tmp- and /etc-hosted stub paths are not re-prefixed.
    sed \
        -e "s|python3 /run/context/build_scripts/scripts/read-packages|python3 ${READ_PACKAGES}|g" \
        -e "s|/run/context/build_scripts/packages/base.toml|${PKGS_TOML}|g" \
        -e "s|/run/context/build_scripts/scripts/kernel-swap.sh|${STUB_BIN}/kernel-swap|g" \
        -e "s|/etc/yum.repos.d/|${TEST_ROOT}/etc/yum.repos.d/|g" \
        "${BASE_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"
    export PATCHED_SCRIPT
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Script smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "image-base: exits 0 with stubs" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# GNOME 50 repo handling — the silent-empty-path regression the issue flags
# ──────────────────────────────────────────────────────────────────────────────

@test "image-base: appends exclude=libjxl* to the found GNOME 50 repo file" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q '^exclude=libjxl\*$' "${TEST_ROOT}/etc/yum.repos.d/jreilly1821-c10s-gnome-50.repo"
}

@test "image-base: fails when the GNOME 50 repo file is not found" {
    rm -f "${TEST_ROOT}/etc/yum.repos.d/jreilly1821-c10s-gnome-50.repo"
    run bash "${PATCHED_SCRIPT}"
    # find returns empty, so the append target is "" and the write fails under
    # `set -e` — a broken desktop, exactly the regression the issue warns about.
    [ "$status" -ne 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# versionlock — the pinned set must be unchanged
# ──────────────────────────────────────────────────────────────────────────────

@test "image-base: versionlocks the GNOME skew packages" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "dnf versionlock add glib2 fontconfig" "${DNF_LOG}"
}

@test "image-base: versionlocks the full kernel set" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "dnf versionlock add kernel kernel-devel kernel-devel-matched kernel-core kernel-modules kernel-modules-core kernel-modules-extra kernel-uki-virt" "${DNF_LOG}"
}

@test "image-base: upgrades glib2 and fontconfig before the GNOME group install" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "dnf -y upgrade glib2 fontconfig" "${DNF_LOG}"
    upgrade_line=$(grep -n "dnf -y upgrade glib2 fontconfig" "${DNF_LOG}" | head -1 | cut -d: -f1)
    group_line=$(grep -n "dnf group install" "${DNF_LOG}" | head -1 | cut -d: -f1)
    [ "$upgrade_line" -lt "$group_line" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# GNOME group + per-package install built from read-packages
# ──────────────────────────────────────────────────────────────────────────────

@test "image-base: installs the GNOME groups with --nobest and exclusions" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "dnf group install -y --nobest" "${DNF_LOG}"
    grep -q -- "-x gnome-software" "${DNF_LOG}"
}

@test "image-base: installs per-package GNOME entries from base.toml" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q -- " gdm" "${DNF_LOG}"
}

@test "image-base: erases centos-logos before installing generic-logos" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "rpm --erase --nodeps centos-logos" "${DNF_LOG}"
    grep -q "rpm --erase --nodeps --nodb generic-logos" "${DNF_LOG}"
}
