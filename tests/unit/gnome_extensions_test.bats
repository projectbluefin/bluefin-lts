#!/usr/bin/env bats

# Unit tests for build_scripts/21-build-gnome-extensions.sh
# Run with: bats tests/unit/gnome_extensions_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
EXT_SCRIPT="${SCRIPT_DIR}/../../build_scripts/21-build-gnome-extensions.sh"

EXT_ROOT_REL="usr/share/gnome-shell/extensions"
GLIB_SCHEMAS_REL="usr/share/glib-2.0/schemas"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    CMD_LOG="${TEST_ROOT}/commands.log"

    EXT_ROOT="${TEST_ROOT}/${EXT_ROOT_REL}"
    GLIB_SCHEMAS="${TEST_ROOT}/${GLIB_SCHEMAS_REL}"

    mkdir -p "${STUB_BIN}" "${EXT_ROOT}" "${GLIB_SCHEMAS}"

    # Extensions that only need their schemas compiled in place
    for uuid in \
        "appindicatorsupport@rgcjonas.gmail.com" \
        "custom-command-list@storageb.github.com" \
        "search-light@icedman.github.com" \
        "dash-to-dock@micxgx.gmail.com"; do
        mkdir -p "${EXT_ROOT}/${uuid}/schemas"
    done

    # Bazaar and Caffeine are staged under extensions/tmp and moved into place
    mkdir -p "${EXT_ROOT}/tmp/bazaar-integration@kolunmi.github.io/src"
    echo "bazaar" > "${EXT_ROOT}/tmp/bazaar-integration@kolunmi.github.io/src/extension.js"
    mkdir -p "${EXT_ROOT}/bazaar-integration@kolunmi.github.io"
    mkdir -p "${EXT_ROOT}/tmp/caffeine/caffeine@patapon.info/schemas"

    # Blur My Shell builds a zip into build/ then unpacks it over itself
    mkdir -p "${EXT_ROOT}/blur-my-shell@aunetx/build" \
             "${EXT_ROOT}/blur-my-shell@aunetx/schemas"
    touch "${EXT_ROOT}/blur-my-shell@aunetx/build/blur-my-shell@aunetx.shell-extension.zip"

    # Gradia builds its own zip via build.sh
    mkdir -p "${EXT_ROOT}/gradia-integration@alexandervanhee.github.io/schemas"
    cat > "${EXT_ROOT}/gradia-integration@alexandervanhee.github.io/build.sh" <<EOF
#!/usr/bin/env bash
echo "gradia-build \$*" >> "${CMD_LOG}"
touch "${EXT_ROOT}/gradia-integration@alexandervanhee.github.io/gradia-integration@alexandervanhee.github.io.shell-extension.zip"
EOF
    chmod +x "${EXT_ROOT}/gradia-integration@alexandervanhee.github.io/build.sh"

    mkdir -p "${EXT_ROOT}/gsconnect@andyholmes.github.io"

    # The compiled schema cache the script deletes before recompiling
    touch "${GLIB_SCHEMAS}/gschemas.compiled"

    # Logging stubs for every external tool the script shells out to
    for tool in dnf glib-compile-schemas make meson; do
        cat > "${STUB_BIN}/${tool}" <<EOF
#!/usr/bin/env bash
echo "${tool} \$*" >> "${CMD_LOG}"
exit 0
EOF
        chmod +x "${STUB_BIN}/${tool}"
    done

    # unzip stub records build-artifact extraction.
    cat > "${STUB_BIN}/unzip" <<EOF
#!/usr/bin/env bash
echo "unzip \${*}" >> "${CMD_LOG}"
exit 0
EOF
    chmod +x "${STUB_BIN}/unzip"

    export PATH="${STUB_BIN}:${PATH}"

    # Rewrite the script's absolute paths into the sandbox
    PATCHED_SCRIPT="${TEST_ROOT}/build-gnome-extensions-patched.sh"
    sed \
        -e "s|/usr/share/gnome-shell/extensions|${EXT_ROOT}|g" \
        -e "s|/usr/share/glib-2.0/schemas|${GLIB_SCHEMAS}|g" \
        -e "s|--prefix=/usr |--prefix=${TEST_ROOT}/usr |g" \
        "${EXT_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"

    export TEST_ROOT STUB_BIN CMD_LOG EXT_ROOT GLIB_SCHEMAS PATCHED_SCRIPT
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

run_script() {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Script smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "gnome-extensions: script exits 0 with stubs" {
    run_script
}

@test "gnome-extensions: script emits a group header naming itself" {
    run_script
    [[ "$output" == *"::group:: ===$(basename "${PATCHED_SCRIPT}")==="* ]]
}

@test "gnome-extensions: script closes the group" {
    run_script
    [[ "$output" == *"::endgroup::"* ]]
}

# ──────────────────────────────────────────────────────────────────────────────
# Build toolchain install/removal
# ──────────────────────────────────────────────────────────────────────────────

@test "gnome-extensions: installs the build toolchain" {
    run_script
    grep -q "dnf -y install glib2-devel meson sassc cmake dbus-devel" "${CMD_LOG}"
}

@test "gnome-extensions: removes the build toolchain before finishing" {
    run_script
    grep -q "dnf -y remove glib2-devel meson sassc cmake dbus-devel" "${CMD_LOG}"
}

@test "gnome-extensions: toolchain removal happens after the install" {
    run_script
    install_line=$(grep -n "dnf -y install" "${CMD_LOG}" | head -1 | cut -d: -f1)
    remove_line=$(grep -n "dnf -y remove" "${CMD_LOG}" | head -1 | cut -d: -f1)
    [ "$remove_line" -gt "$install_line" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Per-extension schema compilation
# ──────────────────────────────────────────────────────────────────────────────

@test "gnome-extensions: compiles AppIndicator schemas strictly" {
    run_script
    grep -q -- "glib-compile-schemas --strict ${EXT_ROOT}/appindicatorsupport@rgcjonas.gmail.com/schemas" "${CMD_LOG}"
}

@test "gnome-extensions: compiles Blur My Shell schemas strictly" {
    run_script
    grep -q -- "glib-compile-schemas --strict ${EXT_ROOT}/blur-my-shell@aunetx/schemas" "${CMD_LOG}"
}

@test "gnome-extensions: compiles Caffeine schemas strictly" {
    run_script
    grep -q -- "glib-compile-schemas --strict ${EXT_ROOT}/caffeine@patapon.info/schemas" "${CMD_LOG}"
}

@test "gnome-extensions: compiles Dash to Dock schemas strictly" {
    run_script
    grep -q -- "glib-compile-schemas --strict ${EXT_ROOT}/dash-to-dock@micxgx.gmail.com/schemas" "${CMD_LOG}"
}

@test "gnome-extensions: compiles Custom Command Menu schemas strictly" {
    run_script
    grep -q -- "glib-compile-schemas --strict ${EXT_ROOT}/custom-command-list@storageb.github.com/schemas" "${CMD_LOG}"
}

@test "gnome-extensions: compiles Search Light schemas strictly" {
    run_script
    grep -q -- "glib-compile-schemas --strict ${EXT_ROOT}/search-light@icedman.github.com/schemas" "${CMD_LOG}"
}

@test "gnome-extensions: compiles Gradia schemas strictly" {
    run_script
    grep -q -- "glib-compile-schemas --strict ${EXT_ROOT}/gradia-integration@alexandervanhee.github.io/schemas" "${CMD_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# Extensions staged under extensions/tmp
# ──────────────────────────────────────────────────────────────────────────────

@test "gnome-extensions: Bazaar sources are moved into the extension directory" {
    run_script
    [ -f "${EXT_ROOT}/bazaar-integration@kolunmi.github.io/src/extension.js" ]
}

@test "gnome-extensions: Caffeine is moved out of the staging directory" {
    run_script
    [ -d "${EXT_ROOT}/caffeine@patapon.info/schemas" ]
}

@test "gnome-extensions: the staging directory is removed at the end" {
    run_script
    [ ! -d "${EXT_ROOT}/tmp" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Source-built extensions
# ──────────────────────────────────────────────────────────────────────────────

@test "gnome-extensions: builds Blur My Shell with make" {
    run_script
    grep -q -- "make -C ${EXT_ROOT}/blur-my-shell@aunetx" "${CMD_LOG}"
}

@test "gnome-extensions: unpacks the Blur My Shell build artifact over the extension" {
    run_script
    grep -q -- "unzip -o ${EXT_ROOT}/blur-my-shell@aunetx/build/blur-my-shell@aunetx.shell-extension.zip -d ${EXT_ROOT}/blur-my-shell@aunetx" "${CMD_LOG}"
}

@test "gnome-extensions: removes the Blur My Shell build directory" {
    run_script
    [ ! -d "${EXT_ROOT}/blur-my-shell@aunetx/build" ]
}

@test "gnome-extensions: builds Dash to Dock with make" {
    run_script
    grep -q -- "make -C ${EXT_ROOT}/dash-to-dock@micxgx.gmail.com" "${CMD_LOG}"
}

@test "gnome-extensions: runs the Gradia build script" {
    run_script
    grep -q "gradia-build" "${CMD_LOG}"
}

@test "gnome-extensions: removes the Gradia release zip after unpacking" {
    run_script
    [ ! -f "${EXT_ROOT}/gradia-integration@alexandervanhee.github.io/gradia-integration@alexandervanhee.github.io.shell-extension.zip" ]
}

@test "gnome-extensions: configures GSConnect with meson into _build" {
    run_script
    grep -q -- "meson setup .* ${EXT_ROOT}/gsconnect@andyholmes.github.io ${EXT_ROOT}/gsconnect@andyholmes.github.io/_build" "${CMD_LOG}"
}

@test "gnome-extensions: installs GSConnect skipping subprojects" {
    run_script
    grep -q -- "meson install -C ${EXT_ROOT}/gsconnect@andyholmes.github.io/_build --skip-subprojects" "${CMD_LOG}"
}

# ──────────────────────────────────────────────────────────────────────────────
# System schema cache rebuild
# ──────────────────────────────────────────────────────────────────────────────

@test "gnome-extensions: stale gschemas.compiled is deleted before recompiling" {
    run_script
    grep -q -- "glib-compile-schemas ${GLIB_SCHEMAS}$" "${CMD_LOG}"
}

@test "gnome-extensions: system schema recompile is not --strict" {
    run_script
    ! grep -q -- "glib-compile-schemas --strict ${GLIB_SCHEMAS}$" "${CMD_LOG}"
}
