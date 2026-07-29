#!/usr/bin/env bats

# Unit tests for build_scripts/21-build-gnome-extensions.sh.
# Run with: bats tests/unit/build_gnome_extensions_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
SOURCE_SCRIPT="${SCRIPT_DIR}/../../build_scripts/21-build-gnome-extensions.sh"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    COMMAND_LOG="${TEST_ROOT}/commands.log"
    mkdir -p "${STUB_BIN}"

    for command in dnf glib-compile-schemas make unzip meson rm mv; do
        cat > "${STUB_BIN}/${command}" <<'EOF'
#!/usr/bin/env bash
printf '%s %s\n' "$(basename "$0")" "$*" >> "${COMMAND_LOG}"
exit 0
EOF
        chmod +x "${STUB_BIN}/${command}"
    done

    cat > "${STUB_BIN}/gradia-build" <<'EOF'
#!/usr/bin/env bash
printf 'gradia-build %s\n' "$*" >> "${COMMAND_LOG}"
exit 0
EOF
    chmod +x "${STUB_BIN}/gradia-build"

    PATCHED_SCRIPT="${TEST_ROOT}/build-gnome-extensions.sh"
    sed \
        -e "s|bash /usr/share/gnome-shell/extensions/gradia-integration@alexandervanhee.github.io/build.sh|gradia-build|" \
        "${SOURCE_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"
    export COMMAND_LOG PATCHED_SCRIPT STUB_BIN
    export PATH="${STUB_BIN}:${PATH}"
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

@test "build-gnome-extensions: runs each build tool and cleans temporary extensions" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q '^glib-compile-schemas ' "${COMMAND_LOG}"
    grep -q '^make ' "${COMMAND_LOG}"
    grep -q '^unzip ' "${COMMAND_LOG}"
    grep -q '^meson setup ' "${COMMAND_LOG}"
    grep -q '^meson install ' "${COMMAND_LOG}"
    grep -q '^gradia-build ' "${COMMAND_LOG}"
    grep -q '^rm -rf /usr/share/gnome-shell/extensions/tmp$' "${COMMAND_LOG}"
}

@test "build-gnome-extensions: propagates build failures" {
    cat > "${STUB_BIN}/make" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
    chmod +x "${STUB_BIN}/make"

    run bash "${PATCHED_SCRIPT}"
    [ "$status" -ne 0 ]
}
