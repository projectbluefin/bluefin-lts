#!/usr/bin/env bats

# Unit tests for build_scripts/scripts/read-packages.
# Run with: bats tests/unit/read_packages_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
READ_PACKAGES="${SCRIPT_DIR}/../../build_scripts/scripts/read-packages"

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/sandbox"
    mkdir -p "${TEST_ROOT}"
    cat > "${TEST_ROOT}/packages.toml" <<'EOF'
[install]
packages = ["bash", "curl"]

[remove]
packages = ["old-package"]
EOF
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

@test "read-packages: prints package names from a section" {
    run python3 "${READ_PACKAGES}" "${TEST_ROOT}/packages.toml" install
    [ "$status" -eq 0 ]
    [ "$output" = $'bash\ncurl' ]
}

@test "read-packages: rejects an unknown section" {
    run python3 "${READ_PACKAGES}" "${TEST_ROOT}/packages.toml" missing
    [ "$status" -eq 1 ]
    [[ "$output" == *"section 'missing' not found"* ]]
}

@test "read-packages: requires a manifest and section" {
    run python3 "${READ_PACKAGES}"
    [ "$status" -eq 1 ]
    [[ "$output" == *"Usage:"* ]]
}
