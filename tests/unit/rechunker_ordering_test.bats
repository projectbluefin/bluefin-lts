#!/usr/bin/env bats

# Regression tests for the LTS full-unit shadow that removes the
# local-fs.target cycle from rechunker-group-fix.service while retaining its
# sysusers ordering.

REPO_ROOT="${BATS_TEST_DIRNAME}/../.."
X86_UNIT="${REPO_ROOT}/system_files_overrides/x86_64/usr/lib/systemd/system/rechunker-group-fix.service"
AARCH64_UNIT="${REPO_ROOT}/system_files_overrides/aarch64/usr/lib/systemd/system/rechunker-group-fix.service"
SERVICES_SCRIPT="${REPO_ROOT}/build_scripts/40-services.sh"

assert_rechunker_unit_is_cycle_safe() {
    local unit="$1"

    grep -q '^DefaultDependencies=no$' "${unit}"
    grep -q '^After=bootc-sysusers-shadow-sync.service$' "${unit}"
    grep -q '^Before=systemd-sysusers.service local-fs-pre.target$' "${unit}"

    run bash -c "grep -v '^#' '${unit}' | grep -E '(^|[[:space:]])local-fs\.target([[:space:]]|$)'"
    [ "${status}" -ne 0 ]

    grep -q '^ExecStart=-systemd-tmpfiles --create --remove --boot --exclude-prefix=/dev$' "${unit}"
}

@test "rechunker ordering: x86_64 full-unit shadow is cycle safe" {
    assert_rechunker_unit_is_cycle_safe "${X86_UNIT}"
}

@test "rechunker ordering: aarch64 full-unit shadow is cycle safe" {
    assert_rechunker_unit_is_cycle_safe "${AARCH64_UNIT}"
}

@test "rechunker ordering: architecture shadows remain identical" {
    run cmp -s "${X86_UNIT}" "${AARCH64_UNIT}"
    [ "${status}" -eq 0 ]
}

@test "rechunker ordering: service remains enabled in the image" {
    grep -q '^systemctl enable rechunker-group-fix.service$' "${SERVICES_SCRIPT}"
}
