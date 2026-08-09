#!/usr/bin/env bats

# Documents the known-broken state of bluefin-lts-countme.service.
# The service runs `/usr/bin/dnf5 makecache`, but dnf5 is uninstallable on
# CentOS Stream 10: not in base/AppStream/CRB/EPEL/hyperscale, and no COPR
# ships epel-10 builds (verified 2026-08-09). dnf4 is present but its
# countme path is what rpm-ostree-countme already failed with
# (coreos/rpm-ostree#5464). Until dnf5 is packaged for EL10 or the service
# is reimplemented, the countme timer cannot succeed.
# Run with: bats tests/unit/countme_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
COUNTME_SERVICE="${SCRIPT_DIR}/../../system_files/usr/lib/systemd/system/bluefin-lts-countme.service"

@test "countme: service unit exists" {
    [ -f "${COUNTME_SERVICE}" ]
}

@test "countme: dnf5 is not installable from base.toml (known missing on EL10)" {
    # If this test starts failing because someone added dnf5 to base.toml,
    # verify it actually exists in CS10/EPEL repos first — as of 2026-08 it
    # does not, and the package install kills the image build.
    ! grep -Eq '^[[:space:]]*"dnf5",' "${SCRIPT_DIR}/../../build_scripts/packages/base.toml"
}
