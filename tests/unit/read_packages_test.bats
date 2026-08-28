#!/usr/bin/env bats

# Unit tests for build_scripts/scripts/read-packages
#
# read-packages is the single reader for build_scripts/packages/base.toml.
# Every package install/remove/exclude list in the image build flows through
# it, so a silent behaviour change here (wrong section lookup, dropped
# packages, non-zero exit) mis-builds the image. packages_test.bats exercises
# it only indirectly through 20-packages.sh; these tests cover the script's own
# argument handling, section lookup and exit codes.
#
# Run with: bats tests/unit/read_packages_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
READ_PACKAGES="${SCRIPT_DIR}/../../build_scripts/scripts/read-packages"
BASE_TOML="${SCRIPT_DIR}/../../build_scripts/packages/base.toml"

setup() {
    MANIFEST="${BATS_TEST_TMPDIR}/manifest.toml"

    cat > "${MANIFEST}" <<'EOF'
[install]
packages = [
    "alpha",
    "bravo",
    "charlie",
]

[remove]
packages = ["delta"]

[empty]
packages = []

[no_packages_key]
other = "value"
EOF
}

run_read_packages() {
    run python3 "${READ_PACKAGES}" "$@"
}

@test "read-packages: script exists and is executable" {
    [ -x "${READ_PACKAGES}" ]
}

@test "read-packages: prints one package per line for a section" {
    run_read_packages "${MANIFEST}" install
    [ "$status" -eq 0 ]
    [ "${#lines[@]}" -eq 3 ]
    [ "${lines[0]}" = "alpha" ]
    [ "${lines[1]}" = "bravo" ]
    [ "${lines[2]}" = "charlie" ]
}

@test "read-packages: preserves manifest ordering" {
    run_read_packages "${MANIFEST}" install
    [ "$status" -eq 0 ]
    [ "$output" = "alpha
bravo
charlie" ]
}

@test "read-packages: reads a single-entry inline section" {
    run_read_packages "${MANIFEST}" remove
    [ "$status" -eq 0 ]
    [ "$output" = "delta" ]
}

@test "read-packages: an empty package list yields no output and exit 0" {
    run_read_packages "${MANIFEST}" empty
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "read-packages: a section without a packages key yields no output and exit 0" {
    run_read_packages "${MANIFEST}" no_packages_key
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "read-packages: exits 1 when the section is missing" {
    run_read_packages "${MANIFEST}" does_not_exist
    [ "$status" -eq 1 ]
    [[ "$output" == *"section 'does_not_exist' not found"* ]]
}

@test "read-packages: section lookup is case sensitive" {
    run_read_packages "${MANIFEST}" INSTALL
    [ "$status" -eq 1 ]
}

@test "read-packages: exits 1 with usage text when no arguments are given" {
    run_read_packages
    [ "$status" -eq 1 ]
    [[ "$output" == *"Usage:"* ]]
    [[ "$output" == *"<manifest.toml> <section>"* ]]
}

@test "read-packages: exits 1 with usage text when the section argument is missing" {
    run_read_packages "${MANIFEST}"
    [ "$status" -eq 1 ]
    [[ "$output" == *"Usage:"* ]]
}

@test "read-packages: exits 1 with usage text when given extra arguments" {
    run_read_packages "${MANIFEST}" install extra
    [ "$status" -eq 1 ]
    [[ "$output" == *"Usage:"* ]]
}

@test "read-packages: fails when the manifest file does not exist" {
    run_read_packages "${BATS_TEST_TMPDIR}/absent.toml" install
    [ "$status" -ne 0 ]
}

@test "read-packages: fails on a malformed manifest" {
    printf 'this is not = valid = toml\n' > "${BATS_TEST_TMPDIR}/bad.toml"
    run_read_packages "${BATS_TEST_TMPDIR}/bad.toml" install
    [ "$status" -ne 0 ]
}

@test "read-packages: reads the real base.toml [install] section" {
    run_read_packages "${BASE_TOML}" install
    [ "$status" -eq 0 ]
    [ "${#lines[@]}" -gt 0 ]
}

@test "read-packages: every section referenced by base.toml resolves" {
    for section in gnome gnome_excluded install install_excluded remove versionlock_gnome; do
        run_read_packages "${BASE_TOML}" "${section}"
        [ "$status" -eq 0 ]
    done
}

@test "read-packages: emits no empty lines for the real base.toml" {
    run_read_packages "${BASE_TOML}" install
    [ "$status" -eq 0 ]
    for line in "${lines[@]}"; do
        [ -n "$line" ]
    done
}
