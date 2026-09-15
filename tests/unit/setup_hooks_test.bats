#!/usr/bin/env bats

# Unit tests for the base first-boot setup hooks shipped in system_files/:
#   system_files/usr/share/ublue-os/privileged-setup.hooks.d/10-tailscale.sh
#   system_files/usr/share/ublue-os/privileged-setup.hooks.d/99-flatpaks.sh
#   system_files/usr/share/ublue-os/user-setup.hooks.d/99-privileged.sh
#
# Run with: bats tests/unit/setup_hooks_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}/../.."
TAILSCALE_HOOK="${REPO_ROOT}/system_files/usr/share/ublue-os/privileged-setup.hooks.d/10-tailscale.sh"
FLATPAKS_HOOK="${REPO_ROOT}/system_files/usr/share/ublue-os/privileged-setup.hooks.d/99-flatpaks.sh"
PRIVILEGED_HOOK="${REPO_ROOT}/system_files/usr/share/ublue-os/user-setup.hooks.d/99-privileged.sh"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    CMD_LOG="${TEST_ROOT}/cmd.log"
    LIBSETUP="${TEST_ROOT}/usr/lib/ublue/setup-services/libsetup.sh"

    mkdir -p "${STUB_BIN}" "${TEST_ROOT}/usr/lib/ublue/setup-services"
    : > "${CMD_LOG}"

    # Stand-in for libsetup.sh. version-script is the real gate the hooks use to
    # decide whether their versioned payload has already been applied.
    cat > "${LIBSETUP}" <<EOF
version-script() {
    echo "version-script \$*" >> "${CMD_LOG}"
    return \${VERSION_SCRIPT_RC:-0}
}
EOF

    _stub() {
        cat > "${STUB_BIN}/$1" <<EOF
#!/usr/bin/env bash
echo "$1 \$*" >> "${CMD_LOG}"
${2:-exit 0}
EOF
        chmod +x "${STUB_BIN}/$1"
    }

    export PATH="${STUB_BIN}:${PATH}"
    export TEST_ROOT STUB_BIN CMD_LOG LIBSETUP
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

_patch() {
    local src="$1" out="${TEST_ROOT}/patched-$(basename "$1")"
    shift
    sed "$@" \
        -e "s|/usr/lib/ublue/setup-services/libsetup.sh|${LIBSETUP}|g" \
        "${src}" > "${out}"
    chmod +x "${out}"
    echo "${out}"
}

# ──────────────────────────────────────────────────────────────────────────────
# 10-tailscale.sh — hands the Tailscale operator role to the invoking user
# ──────────────────────────────────────────────────────────────────────────────

_patch_tailscale() {
    _stub tailscale "${TAILSCALE_RC_BODY:-exit 0}"
    cat > "${STUB_BIN}/getent" <<EOF
#!/usr/bin/env bash
echo "getent \$*" >> "${CMD_LOG}"
[ "\${GETENT_RC:-0}" -eq 0 ] || exit "\${GETENT_RC}"
echo "bluefin-user:x:\$3:\$3::/var/home/bluefin-user:/bin/bash"
EOF
    chmod +x "${STUB_BIN}/getent"
    _patch "${TAILSCALE_HOOK}"
}

@test "tailscale hook: gates on version-script tailscale-lts privileged 1" {
    script="$(_patch_tailscale)"
    PKEXEC_UID=1000 run bash "${script}"
    [ "$status" -eq 0 ]
    grep -qx "version-script tailscale-lts privileged 1" "${CMD_LOG}"
}

@test "tailscale hook: sets the operator to the PKEXEC_UID account name" {
    script="$(_patch_tailscale)"
    PKEXEC_UID=1000 run bash "${script}"
    [ "$status" -eq 0 ]
    grep -qx "getent passwd 1000" "${CMD_LOG}"
    grep -qx "tailscale set --operator=bluefin-user" "${CMD_LOG}"
}

@test "tailscale hook: exits 0 without touching tailscale when already versioned" {
    script="$(_patch_tailscale)"
    PKEXEC_UID=1000 VERSION_SCRIPT_RC=1 run bash "${script}"
    [ "$status" -eq 0 ]
    ! grep -q "^tailscale " "${CMD_LOG}"
}

# Characterization test. `set -u` only kills the command substitution subshell,
# so an unset PKEXEC_UID does not abort the hook: it hands tailscale an EMPTY
# operator and still reports success, while version-script has already recorded
# the hook as applied, so it never runs again. Flip this test when the hook
# learns to fail closed.
@test "tailscale hook: unset PKEXEC_UID yields an empty --operator and still exits 0" {
    script="$(_patch_tailscale)"
    run env -u PKEXEC_UID bash "${script}"
    [ "$status" -eq 0 ]
    grep -qx "tailscale set --operator=" "${CMD_LOG}"
}

@test "tailscale hook: fails when the tailscale call fails" {
    script="$(TAILSCALE_RC_BODY='exit 1' _patch_tailscale)"
    PKEXEC_UID=1000 run bash "${script}"
    [ "$status" -ne 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# 99-flatpaks.sh — seeds the Firefox system config into the flatpak extension
# ──────────────────────────────────────────────────────────────────────────────

_flatpak_pref_dir() {
    echo "${TEST_ROOT}/var/lib/flatpak/extension/org.mozilla.firefox.systemconfig/$1/stable/defaults/pref"
}

_patch_flatpaks() {
    _stub arch "echo \"${1:-x86_64}\""
    mkdir -p "${TEST_ROOT}/usr/share/ublue-os/firefox-config"
    echo 'pref("bluefin.configured", true);' \
        > "${TEST_ROOT}/usr/share/ublue-os/firefox-config/bluefin-prefs.js"
    _patch "${FLATPAKS_HOOK}" \
        -e "s|/var/lib/flatpak|${TEST_ROOT}/var/lib/flatpak|g" \
        -e "s|/usr/share/ublue-os/firefox-config|${TEST_ROOT}/usr/share/ublue-os/firefox-config|g"
}

@test "flatpaks hook: gates on version-script flatpaks-lts privileged 1" {
    script="$(_patch_flatpaks)"
    run bash "${script}"
    [ "$status" -eq 0 ]
    grep -qx "version-script flatpaks-lts privileged 1" "${CMD_LOG}"
}

@test "flatpaks hook: creates the arch-specific Firefox pref directory" {
    script="$(_patch_flatpaks x86_64)"
    run bash "${script}"
    [ "$status" -eq 0 ]
    [ -d "$(_flatpak_pref_dir x86_64)" ]
}

@test "flatpaks hook: copies the shipped firefox-config prefs into the extension" {
    script="$(_patch_flatpaks x86_64)"
    run bash "${script}"
    [ "$status" -eq 0 ]
    grep -q 'bluefin.configured' "$(_flatpak_pref_dir x86_64)/bluefin-prefs.js"
}

@test "flatpaks hook: keys the destination path off arch, not a hardcoded x86_64" {
    script="$(_patch_flatpaks ppc64le)"
    run bash "${script}"
    [ "$status" -eq 0 ]
    [ -f "$(_flatpak_pref_dir ppc64le)/bluefin-prefs.js" ]
    [ ! -d "$(_flatpak_pref_dir x86_64)" ]
}

@test "flatpaks hook: skips the Firefox seeding entirely on aarch64" {
    script="$(_patch_flatpaks aarch64)"
    run bash "${script}"
    [ "$status" -eq 0 ]
    [ ! -d "${TEST_ROOT}/var/lib/flatpak" ]
}

@test "flatpaks hook: does no work when already versioned" {
    script="$(_patch_flatpaks x86_64)"
    VERSION_SCRIPT_RC=1 run bash "${script}"
    [ "$status" -eq 0 ]
    [ ! -d "${TEST_ROOT}/var/lib/flatpak" ]
}

@test "flatpaks hook: overwrites a pref file left by an earlier image" {
    script="$(_patch_flatpaks x86_64)"
    mkdir -p "$(_flatpak_pref_dir x86_64)"
    echo 'stale' > "$(_flatpak_pref_dir x86_64)/bluefin-prefs.js"
    run bash "${script}"
    [ "$status" -eq 0 ]
    grep -q 'bluefin.configured' "$(_flatpak_pref_dir x86_64)/bluefin-prefs.js"
    ! grep -q 'stale' "$(_flatpak_pref_dir x86_64)/bluefin-prefs.js"
}

# ──────────────────────────────────────────────────────────────────────────────
# 99-privileged.sh — user-setup hook that escalates into the privileged units
# ──────────────────────────────────────────────────────────────────────────────

_patch_privileged() {
    _stub pkexec "${1:-exit 0}"
    _patch "${PRIVILEGED_HOOK}"
}

@test "privileged hook: escalates to ublue-privileged-setup through pkexec" {
    script="$(_patch_privileged)"
    run bash "${script}"
    [ "$status" -eq 0 ]
    grep -qx "pkexec /usr/bin/ublue-privileged-setup" "${CMD_LOG}"
}

@test "privileged hook: announces the run so setup logs are attributable" {
    script="$(_patch_privileged)"
    run bash "${script}"
    [ "$status" -eq 0 ]
    [[ "${output}" == *"Running all privileged units"* ]]
}

@test "privileged hook: propagates a pkexec failure instead of reporting success" {
    script="$(_patch_privileged 'exit 3')"
    run bash "${script}"
    [ "$status" -ne 0 ]
}
