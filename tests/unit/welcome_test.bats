#!/usr/bin/env bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
WELCOME_SCRIPT="${SCRIPT_DIR}/../../build_scripts/25-welcome.sh"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    mkdir -p "${TEST_ROOT}/etc/profile.d" "${TEST_ROOT}/usr/bin"

    cat > "${TEST_ROOT}/etc/profile.d/uwelcome.sh" <<'EOF'
#!/usr/bin/env bash
if [ "$(id -u)" != "0" ] && [ -z "${UWELCOME_SHOWN-}" ]; then
    UWELCOME_SHOWN=1
    export UWELCOME_SHOWN
    uwelcome
fi
EOF
    touch "${TEST_ROOT}/usr/bin/uwelcome" "${TEST_ROOT}/usr/bin/umotd"
    chmod +x "${TEST_ROOT}/usr/bin/uwelcome" "${TEST_ROOT}/usr/bin/umotd"

    PATCHED_SCRIPT="${TEST_ROOT}/25-welcome-patched.sh"
    sed \
        -e "s|/etc/profile.d/uwelcome.sh|${TEST_ROOT}/etc/profile.d/uwelcome.sh|g" \
        -e "s|/usr/bin/uwelcome|${TEST_ROOT}/usr/bin/uwelcome|g" \
        -e "s|/usr/bin/umotd|${TEST_ROOT}/usr/bin/umotd|g" \
        "${WELCOME_SCRIPT}" > "${PATCHED_SCRIPT}"
}

@test "welcome: requires an interactive shell before setting the dedupe marker" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -F 'if [[ $- == *i* ]] && [ "$(id -u)" != "0" ] && [ -z "${UWELCOME_SHOWN-}" ]; then' \
        "${TEST_ROOT}/etc/profile.d/uwelcome.sh"
}

@test "welcome: fails if the inherited profile hook changes unexpectedly" {
    sed -i 's/UWELCOME_SHOWN/WELCOME_ALREADY_SHOWN/g' "${TEST_ROOT}/etc/profile.d/uwelcome.sh"
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -ne 0 ]
}

@test "welcome: fails if uwelcome is missing" {
    rm "${TEST_ROOT}/usr/bin/uwelcome"
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -ne 0 ]
}

@test "welcome: fails if umotd is missing" {
    rm "${TEST_ROOT}/usr/bin/umotd"
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -ne 0 ]
}
