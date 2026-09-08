#!/usr/bin/env bats

# Unit tests for build_scripts/21-build-gnome-extensions.sh
# Run with: bats tests/unit/build_gnome_extensions_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
EXTENSIONS_SCRIPT="${SCRIPT_DIR}/../../build_scripts/21-build-gnome-extensions.sh"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    CMD_LOG="${TEST_ROOT}/cmd.log"
    DNF_LOG="${TEST_ROOT}/dnf.log"

    mkdir -p "${STUB_BIN}"
    mkdir -p "${TEST_ROOT}/usr/share/gnome-shell/extensions/tmp/bazaar-integration@kolunmi.github.io/src"
    mkdir -p "${TEST_ROOT}/usr/share/gnome-shell/extensions/tmp/caffeine/caffeine@patapon.info/schemas"
    mkdir -p "${TEST_ROOT}/usr/share/gnome-shell/extensions/appindicatorsupport@rgcjonas.gmail.com/schemas"
    mkdir -p "${TEST_ROOT}/usr/share/gnome-shell/extensions/blur-my-shell@aunetx/build"
    mkdir -p "${TEST_ROOT}/usr/share/gnome-shell/extensions/blur-my-shell@aunetx/schemas"
    mkdir -p "${TEST_ROOT}/usr/share/gnome-shell/extensions/dash-to-dock@micxgx.gmail.com/schemas"
    mkdir -p "${TEST_ROOT}/usr/share/gnome-shell/extensions/gradia-integration@alexandervanhee.github.io/schemas"
    mkdir -p "${TEST_ROOT}/usr/share/gnome-shell/extensions/gsconnect@andyholmes.github.io"
    mkdir -p "${TEST_ROOT}/usr/share/gnome-shell/extensions/custom-command-list@storageb.github.com/schemas"
    mkdir -p "${TEST_ROOT}/usr/share/gnome-shell/extensions/search-light@icedman.github.com/schemas"
    mkdir -p "${TEST_ROOT}/usr/share/glib-2.0/schemas"

    touch "${TEST_ROOT}/usr/share/glib-2.0/schemas/gschemas.compiled"

    # dnf stub: record invocations
    cat > "${STUB_BIN}/dnf" <<EOF
#!/usr/bin/env bash
echo "dnf \$*" >> "${DNF_LOG}"
echo "dnf \$*" >> "${CMD_LOG}"
exit 0
EOF

    # generic tool stubs: record invocations
    for cmd in glib-compile-schemas make unzip meson; do
        cat > "${STUB_BIN}/${cmd}" <<EOF
#!/usr/bin/env bash
echo "${cmd} \$*" >> "${CMD_LOG}"
exit 0
EOF
    done

    # gradia-build stub to replace \`bash /usr/share/.../build.sh\`
    cat > "${STUB_BIN}/gradia-build" <<EOF
#!/usr/bin/env bash
echo "gradia-build \$*" >> "${CMD_LOG}"
exit 0
EOF

    chmod +x "${STUB_BIN}"/*
    export PATH="${STUB_BIN}:${PATH}"

    # Patch absolute paths to TEST_ROOT
    PATCHED_SCRIPT="${TEST_ROOT}/build-gnome-extensions-patched.sh"
    sed \
        -e "s|bash /usr/share/gnome-shell/extensions/gradia-integration@alexandervanhee.github.io/build.sh|${STUB_BIN}/gradia-build|g" \
        -e "s|/usr/share/gnome-shell/extensions|${TEST_ROOT}/usr/share/gnome-shell/extensions|g" \
        -e "s|/usr/share/glib-2.0/schemas|${TEST_ROOT}/usr/share/glib-2.0/schemas|g" \
        "${EXTENSIONS_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"

    export PATCHED_SCRIPT TEST_ROOT STUB_BIN CMD_LOG DNF_LOG
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

run_script() {
    run bash "${PATCHED_SCRIPT}"
}

# Line number of the first command invocation matching a pattern
cmd_line() {
    grep -n -- "$1" "${CMD_LOG}" | head -1 | cut -d: -f1
}

# ──────────────────────────────────────────────────────────────────────────────
# Happy path and error propagation
# ──────────────────────────────────────────────────────────────────────────────

@test "gnome-extensions: exits 0 on the happy path" {
    run_script
    [ "$status" -eq 0 ]
}

@test "gnome-extensions: propagates dnf install failure" {
    cat > "${STUB_BIN}/dnf" <<EOF
#!/usr/bin/env bash
echo "dnf \$*" >> "${DNF_LOG}"
exit 2
EOF
    run_script
    [ "$status" -eq 2 ]
    ! grep -q "meson setup" "${CMD_LOG}"
}

@test "gnome-extensions: propagates build tool failure (make)" {
    cat > "${STUB_BIN}/make" <<EOF
#!/usr/bin/env bash
exit 3
EOF
    run_script
    [ "$status" -eq 3 ]
}

@test "gnome-extensions: propagates meson failure" {
    cat > "${STUB_BIN}/meson" <<EOF
#!/usr/bin/env bash
exit 4
EOF
    run_script
    [ "$status" -eq 4 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Build dependencies lifecycle
# ──────────────────────────────────────────────────────────────────────────────

@test "gnome-extensions: installs required build dependencies at startup" {
    run_script
    [ "$status" -eq 0 ]
    local install_line
    install_line="$(grep "^dnf -y install" "${DNF_LOG}")"
    for pkg in glib2-devel meson sassc cmake dbus-devel; do
        [[ " ${install_line} " == *" ${pkg} "* ]]
    done
}

@test "gnome-extensions: removes build dependencies during cleanup" {
    run_script
    [ "$status" -eq 0 ]
    local remove_line
    remove_line="$(grep "^dnf -y remove" "${DNF_LOG}")"
    for pkg in glib2-devel meson sassc cmake dbus-devel; do
        [[ " ${remove_line} " == *" ${pkg} "* ]]
    done
}

@test "gnome-extensions: installs build tools before building and removes after" {
    run_script
    [ "$status" -eq 0 ]
    local inst_line rm_line first_build_line
    inst_line="$(cmd_line "dnf -y install")"
    rm_line="$(cmd_line "dnf -y remove")"
    first_build_line="$(cmd_line "glib-compile-schemas --strict")"

    [ "${inst_line}" -lt "${first_build_line}" ]
    [ "${first_build_line}" -lt "${rm_line}" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Extension moves and compilations
# ──────────────────────────────────────────────────────────────────────────────

@test "gnome-extensions: compiles AppIndicator schemas strictly" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "glib-compile-schemas --strict .*/appindicatorsupport@rgcjonas.gmail.com/schemas" "${CMD_LOG}"
}

@test "gnome-extensions: moves Bazaar companion from tmp src to destination" {
    run_script
    [ "$status" -eq 0 ]
    [ -d "${TEST_ROOT}/usr/share/gnome-shell/extensions/bazaar-integration@kolunmi.github.io" ]
}

@test "gnome-extensions: builds Blur My Shell and removes build artifacts" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "make -C .*/blur-my-shell@aunetx" "${CMD_LOG}"
    grep -q "unzip -o .*/blur-my-shell@aunetx.shell-extension.zip" "${CMD_LOG}"
    grep -q "glib-compile-schemas --strict .*/blur-my-shell@aunetx/schemas" "${CMD_LOG}"
    [ ! -d "${TEST_ROOT}/usr/share/gnome-shell/extensions/blur-my-shell@aunetx/build" ]
}

@test "gnome-extensions: moves Caffeine from tmp and compiles schemas strictly" {
    run_script
    [ "$status" -eq 0 ]
    [ -d "${TEST_ROOT}/usr/share/gnome-shell/extensions/caffeine@patapon.info" ]
    grep -q "glib-compile-schemas --strict .*/caffeine@patapon.info/schemas" "${CMD_LOG}"
}

@test "gnome-extensions: builds Dash to Dock and compiles schemas strictly" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "make -C .*/dash-to-dock@micxgx.gmail.com" "${CMD_LOG}"
    grep -q "glib-compile-schemas --strict .*/dash-to-dock@micxgx.gmail.com/schemas" "${CMD_LOG}"
}

@test "gnome-extensions: builds Gradia Capture, unzips, and removes zip artifact" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "gradia-build" "${CMD_LOG}"
    grep -q "unzip -o .*/gradia-integration@alexandervanhee.github.io.shell-extension.zip" "${CMD_LOG}"
    grep -q "glib-compile-schemas --strict .*/gradia-integration@alexandervanhee.github.io/schemas" "${CMD_LOG}"
}

@test "gnome-extensions: builds GSConnect with meson and installs skipping subprojects" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "meson setup --prefix=/usr .*/gsconnect@andyholmes.github.io" "${CMD_LOG}"
    grep -q "meson install -C .*/gsconnect@andyholmes.github.io/_build --skip-subprojects" "${CMD_LOG}"
}

@test "gnome-extensions: compiles Custom Command Menu and Search Light schemas" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "glib-compile-schemas --strict .*/custom-command-list@storageb.github.com/schemas" "${CMD_LOG}"
    grep -q "glib-compile-schemas --strict .*/search-light@icedman.github.com/schemas" "${CMD_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Global schema compilation and tmp cleanup
# ──────────────────────────────────────────────────────────────────────────────

@test "gnome-extensions: recompiles global glib schemas after removing stale compiled file" {
    run_script
    [ "$status" -eq 0 ]
    grep -q "glib-compile-schemas ${TEST_ROOT}/usr/share/glib-2.0/schemas" "${CMD_LOG}"
}

@test "gnome-extensions: removes tmp directory on completion" {
    run_script
    [ "$status" -eq 0 ]
    [ ! -d "${TEST_ROOT}/usr/share/gnome-shell/extensions/tmp" ]
}
