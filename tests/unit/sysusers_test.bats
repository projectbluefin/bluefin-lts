#!/usr/bin/env bats

# Regression test for libstoragemgmt's daemon account.
# The libstoragemgmt RPM creates the `libstoragemgmt` user/group via a %pre
# `systemd-sysusers --replace` scriptlet that does not persist through bootc/
# ostree image assembly. Without the group, /usr/lib/tmpfiles.d/libstoragemgmt
# .conf cannot create /run/lsm/ipc and libstoragemgmt.service (lsmd) fails to
# start.
# Run with: bats tests/unit/sysusers_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"

SYSTEM_USERS_FILE="${SCRIPT_DIR}/../../system_files/usr/lib/sysusers.d/libstoragemgmt.conf"

@test "sysusers: libstoragemgmt account definition exists" {
    [ -f "${SYSTEM_USERS_FILE}" ]
}

@test "sysusers: defines the libstoragemgmt daemon user" {
    grep -q '^u libstoragemgmt ' "${SYSTEM_USERS_FILE}"
}
