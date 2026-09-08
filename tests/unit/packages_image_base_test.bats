#!/usr/bin/env bats

# Unit tests for build_scripts/overrides/base/10-packages-image-base.sh
# Run with: bats tests/unit/packages_image_base_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
BASE_SCRIPT="${SCRIPT_DIR}/../../build_scripts/overrides/base/10-packages-image-base.sh"

# Rewrite every absolute path the script touches into the sandbox, then run it.
# Called after the per-test fixture (repo files, stub behaviour) is in place.
patch_and_run() {
    PATCHED_SCRIPT="${TEST_ROOT}/10-packages-image-base-patched.sh"
    sed \
        -e "s|python3 /run/context/build_scripts/scripts/read-packages|${STUB_BIN}/read-packages|g" \
        -e "s|/run/context/build_scripts/packages/base.toml|${TEST_ROOT}/base.toml|g" \
        -e "s|/run/context/build_scripts/scripts/kernel-swap.sh|${STUB_BIN}/kernel-swap.sh|g" \
        -e "s|/etc/yum.repos.d/|${REPOS_DIR}/|g" \
        "${BASE_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"
    run bash "${PATCHED_SCRIPT}"
}

# Line number of the first dnf invocation matching a pattern, for ordering asserts.
dnf_line() {
    grep -n -- "$1" "${DNF_LOG}" | head -1 | cut -d: -f1
}

# Line number of the first command invocation in CMD_LOG matching a pattern.
cmd_line() {
    grep -n -- "$1" "${CMD_LOG}" | head -1 | cut -d: -f1
}

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    REPOS_DIR="${TEST_ROOT}/etc/yum.repos.d"
    DNF_LOG="${TEST_ROOT}/dnf.log"
    CMD_LOG="${TEST_ROOT}/cmd.log"

    mkdir -p "${STUB_BIN}" "${REPOS_DIR}"

    export MAJOR_VERSION_NUMBER="10"

    # When 1, the dnf stub materialises a repo file for --add-repo the way real
    # dnf config-manager does. Tests flip this off to exercise the discovery gap.
    export STUB_ADD_REPO_CREATES=1

    # What the read-packages stub answers for each TOML key.
    export STUB_GNOME_PKGS="gnome-shell gdm nautilus"
    export STUB_GNOME_EXCLUDED_PKGS="gnome-tour totem"

    : > "${TEST_ROOT}/base.toml"

    cat > "${STUB_BIN}/dnf" <<EOF
#!/usr/bin/env bash
echo "dnf \$*" >> "${DNF_LOG}"
echo "dnf \$*" >> "${CMD_LOG}"
if [[ "\$1" == "config-manager" && "\${STUB_ADD_REPO_CREATES}" == "1" ]]; then
    url=""
    prev=""
    for arg in "\$@"; do
        case "\$arg" in
            --add-repo=*) url="\${arg#--add-repo=}" ;;
            *) [[ "\$prev" == "--add-repo" ]] && url="\$arg" ;;
        esac
        prev="\$arg"
    done
    if [[ -n "\$url" ]]; then
        printf 'repo written by stub\n' > "${REPOS_DIR}/\$(basename "\$url")"
    fi
fi
exit 0
EOF

    cat > "${STUB_BIN}/rpm" <<EOF
#!/usr/bin/env bash
echo "rpm \$*" >> "${CMD_LOG}"
exit 0
EOF

    cat > "${STUB_BIN}/kernel-swap.sh" <<EOF
#!/usr/bin/env bash
echo "kernel-swap.sh \$*" >> "${CMD_LOG}"
exit 0
EOF

    cat > "${STUB_BIN}/read-packages" <<EOF
#!/usr/bin/env bash
echo "read-packages \$*" >> "${CMD_LOG}"
case "\$2" in
    gnome) [[ -n "\${STUB_GNOME_PKGS}" ]] && printf '%s\n' \${STUB_GNOME_PKGS} ;;
    gnome_excluded) [[ -n "\${STUB_GNOME_EXCLUDED_PKGS}" ]] && printf '%s\n' \${STUB_GNOME_EXCLUDED_PKGS} ;;
    *) exit 1 ;;
esac
EOF

    chmod +x "${STUB_BIN}"/*
    export PATH="${STUB_BIN}:${PATH}"
    export TEST_ROOT STUB_BIN REPOS_DIR DNF_LOG CMD_LOG
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Script smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "image-base: exits 0 on the happy path" {
    patch_and_run
    [ "$status" -eq 0 ]
}

@test "image-base: fails when MAJOR_VERSION_NUMBER is unset" {
    unset MAJOR_VERSION_NUMBER
    patch_and_run
    [ "$status" -ne 0 ]
    [[ "$output" == *"MAJOR_VERSION_NUMBER"* ]]
}

@test "image-base: propagates a dnf failure instead of continuing" {
    cat > "${STUB_BIN}/dnf" <<EOF
#!/usr/bin/env bash
echo "dnf \$*" >> "${DNF_LOG}"
echo "dnf \$*" >> "${CMD_LOG}"
exit 7
EOF
    chmod +x "${STUB_BIN}/dnf"
    patch_and_run
    [ "$status" -eq 7 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Bootstrap: subscription-manager removal, versionlock plugin, kernel swap
# ──────────────────────────────────────────────────────────────────────────────

@test "image-base: removes subscription-manager with scriptlets disabled" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "dnf remove -y --setopt=tsflags=noscripts subscription-manager" "${DNF_LOG}"
}

@test "image-base: installs the versionlock plugin before locking anything" {
    patch_and_run
    [ "$status" -eq 0 ]
    [ "$(dnf_line "dnf-command(versionlock)")" -lt "$(dnf_line "versionlock add")" ]
}

@test "image-base: runs kernel-swap.sh" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "kernel-swap.sh" "${CMD_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# GNOME 50 COPR repo + libjxl exclusion
# ──────────────────────────────────────────────────────────────────────────────

@test "image-base: adds the GNOME 50 COPR repo for the major version in use" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "config-manager --add-repo .*jreilly1821/c10s-gnome-50/repo/epel-10/jreilly1821-c10s-gnome-50-epel-10.repo" "${DNF_LOG}"
}

@test "image-base: honours a different MAJOR_VERSION_NUMBER in the COPR URL" {
    export MAJOR_VERSION_NUMBER="11"
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "epel-11/jreilly1821-c10s-gnome-50-epel-11.repo" "${DNF_LOG}"
    ! grep -q "epel-10/jreilly1821" "${DNF_LOG}"
}

@test "image-base: appends the libjxl exclusion to the GNOME 50 repo file" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "^exclude=libjxl\*$" "${REPOS_DIR}/jreilly1821-c10s-gnome-50-epel-10.repo"
}

@test "image-base: fails loudly when the GNOME 50 repo file is never created" {
    export STUB_ADD_REPO_CREATES=0
    patch_and_run
    [ "$status" -ne 0 ]
    # Nothing may reach the GNOME group install once the exclusion is lost.
    ! grep -q "gnome-shell" "${DNF_LOG}"
}

@test "image-base: does not touch unrelated repo files" {
    printf 'unrelated\n' > "${REPOS_DIR}/epel.repo"
    patch_and_run
    [ "$status" -eq 0 ]
    [ "$(cat "${REPOS_DIR}/epel.repo")" = "unrelated" ]
}

@test "image-base: excludes libjxl in exactly one repo file when several match" {
    printf 'stale\n' > "${REPOS_DIR}/jreilly1821-c10s-gnome-50-epel-10-copy.repo"
    patch_and_run
    [ "$status" -eq 0 ]
    [ "$(grep -rl "^exclude=libjxl\*$" "${REPOS_DIR}" | wc -l)" -eq 1 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Pre-GNOME upgrades and versionlocks
# ──────────────────────────────────────────────────────────────────────────────

@test "image-base: installs the selinux-policy and gnutls prerequisites" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "dnf -y install selinux-policy selinux-policy-targeted gnutls" "${DNF_LOG}"
}

@test "image-base: upgrades glib2 and fontconfig before the GNOME group install" {
    patch_and_run
    [ "$status" -eq 0 ]
    [ "$(dnf_line "upgrade glib2 fontconfig")" -lt "$(dnf_line "group install")" ]
}

@test "image-base: versionlocks glib2 and fontconfig after upgrading them" {
    patch_and_run
    [ "$status" -eq 0 ]
    [ "$(dnf_line "upgrade glib2 fontconfig")" -lt "$(dnf_line "versionlock add glib2 fontconfig")" ]
}

@test "image-base: versionlocks the whole kernel set" {
    patch_and_run
    [ "$status" -eq 0 ]
    local locked
    locked="$(grep -- "versionlock add kernel" "${DNF_LOG}")"
    for pkg in kernel kernel-devel kernel-devel-matched kernel-core kernel-modules \
        kernel-modules-core kernel-modules-extra kernel-uki-virt; do
        [[ " ${locked} " == *" ${pkg} "* ]]
    done
}

# ──────────────────────────────────────────────────────────────────────────────
# EPEL / multimedia repos
# ──────────────────────────────────────────────────────────────────────────────

@test "image-base: installs epel-release for the major version and enables crb" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "epel/epel-release-latest-10.noarch.rpm" "${DNF_LOG}"
    grep -q -- "config-manager --set-enabled crb" "${DNF_LOG}"
}

@test "image-base: leaves epel-multimedia disabled and only enables it per transaction" {
    patch_and_run
    [ "$status" -eq 0 ]
    [ "$(dnf_line "config-manager --set-disabled epel-multimedia")" -lt "$(dnf_line "--enablerepo=epel-multimedia")" ]
    grep -q -- "--enablerepo=epel-multimedia" "${DNF_LOG}"
}

@test "image-base: installs the multimedia codec set from epel-multimedia" {
    patch_and_run
    [ "$status" -eq 0 ]
    local line
    line="$(grep -- "--enablerepo=epel-multimedia" "${DNF_LOG}")"
    for pkg in ffmpeg libavcodec @multimedia lame libjxl ffmpegthumbnailer; do
        [[ "${line}" == *"${pkg}"* ]]
    done
}

# ──────────────────────────────────────────────────────────────────────────────
# Group install and the GNOME package list
# ──────────────────────────────────────────────────────────────────────────────

@test "image-base: excludes the server-oriented packages from the group install" {
    patch_and_run
    [ "$status" -eq 0 ]
    local line
    line="$(grep -- "group install" "${DNF_LOG}")"
    for excl in "rsyslog\*" cockpit "cronie\*" crontabs PackageKit PackageKit-command-not-found; do
        [[ "${line}" == *"-x ${excl//\\/}"* ]]
    done
}

@test "image-base: group install uses --nobest" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "group install -y --nobest" "${DNF_LOG}"
}

@test "image-base: installs the GNOME packages reported by read-packages" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "read-packages ${TEST_ROOT}/base.toml gnome$" "${CMD_LOG}"
    local line
    line="$(grep -- "gnome-shell" "${DNF_LOG}")"
    for pkg in gnome-shell gdm nautilus; do
        [[ "${line}" == *"${pkg}"* ]]
    done
}

@test "image-base: turns gnome_excluded entries into -x arguments" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "read-packages ${TEST_ROOT}/base.toml gnome_excluded$" "${CMD_LOG}"
    local line
    line="$(grep -- "gnome-shell" "${DNF_LOG}")"
    [[ "${line}" == *"-x gnome-tour"* ]]
    [[ "${line}" == *"-x totem"* ]]
}

@test "image-base: still installs GNOME when the exclusion list is empty" {
    export STUB_GNOME_EXCLUDED_PKGS=""
    patch_and_run
    [ "$status" -eq 0 ]
    local line
    line="$(grep -- "gnome-shell" "${DNF_LOG}")"
    [[ "${line}" != *" -x "* ]]
}

# A read-packages failure is swallowed: readarray consumes a failing process
# substitution without tripping `set -e`, so the GNOME transaction silently
# installs nothing. Pinned here so the day it is made fail-closed is a visible
# test change rather than a silent behaviour flip.
@test "image-base: a read-packages failure produces an empty GNOME install" {
    cat > "${STUB_BIN}/read-packages" <<'EOF'
#!/usr/bin/env bash
exit 3
EOF
    chmod +x "${STUB_BIN}/read-packages"
    patch_and_run
    ! grep -q "gnome-shell" "${DNF_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Desktop payload and logo swap
# ──────────────────────────────────────────────────────────────────────────────

@test "image-base: installs the boot and firmware payload" {
    patch_and_run
    [ "$status" -eq 0 ]
    local line
    line="$(grep -- "plymouth" "${DNF_LOG}")"
    for pkg in plymouth plymouth-system-theme fwupd systemd-resolved systemd-container systemd-oomd; do
        [[ "${line}" == *"${pkg}"* ]]
    done
}

@test "image-base: installs the libcamera brace expansion set" {
    patch_and_run
    [ "$status" -eq 0 ]
    local line
    line="$(grep -- "libcamera" "${DNF_LOG}")"
    for pkg in libcamera libcamera-v4l2 libcamera-gstreamer libcamera-tools; do
        [[ "${line}" == *"${pkg}"* ]]
    done
}

@test "image-base: installs the GNOME 50 compat shim" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "dnf -y install gnome50-el10-compat libgda" "${DNF_LOG}"
}

@test "image-base: removes console-login-helper-messages" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "dnf -y remove console-login-helper-messages" "${DNF_LOG}"
}

@test "image-base: erases centos-logos only after the GNOME group install" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q -- "rpm --erase --nodeps centos-logos" "${CMD_LOG}"
    [ "$(cmd_line "group install")" -lt "$(cmd_line "rpm --erase --nodeps centos-logos")" ]
}

@test "image-base: installs generic-logos then erases it without touching the rpmdb" {
    patch_and_run
    [ "$status" -eq 0 ]
    grep -q "generic-logos-18.0.0-26.fc43.noarch.rpm" "${DNF_LOG}"
    grep -q -- "rpm --erase --nodeps --nodb generic-logos" "${CMD_LOG}"
}
