#!/usr/bin/env bats

# Regression tests for the LTS drop-in that removes the local-fs.target cycle
# from rechunker-group-fix.service while retaining its sysusers ordering.

DROP_IN="${BATS_TEST_DIRNAME}/../../system_files/usr/lib/systemd/system/rechunker-group-fix.service.d/ordering.conf"

@test "rechunker ordering: resets common local-fs dependencies" {
    run grep -E '^After=$|^Wants=$' "${DROP_IN}"
    [ "$status" -eq 0 ]
    [ "$(grep -c '^After=$' "${DROP_IN}")" -eq 1 ]
    [ "$(grep -c '^Wants=$' "${DROP_IN}")" -eq 1 ]
}

@test "rechunker ordering: runs before local-fs-pre and sysusers" {
    grep -q '^After=bootc-sysusers-shadow-sync.service$' "${DROP_IN}"
    grep -q '^Before=systemd-sysusers.service local-fs-pre.target$' "${DROP_IN}"
}

@test "rechunker ordering: does not add local-fs.target" {
    run bash -c "grep -v '^#' '${DROP_IN}' | grep -E '(^|[[:space:]])local-fs\\.target([[:space:]]|$)'"
    [ "$status" -ne 0 ]
}
