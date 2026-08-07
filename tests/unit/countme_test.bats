#!/usr/bin/env bats

# Regression tests for bluefin-lts-countme.service dependencies.
# The service runs `/usr/bin/dnf5 makecache`, but dnf5 is not part of the
# centos-bootc base image — it must be installed by the build, or the
# countme timer fails on every firing.
# Run with: bats tests/unit/countme_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
PKGS_TOML="${SCRIPT_DIR}/../../build_scripts/packages/base.toml"
COUNTME_SERVICE="${SCRIPT_DIR}/../../system_files/usr/lib/systemd/system/bluefin-lts-countme.service"

@test "countme: service unit exists" {
    [ -f "${COUNTME_SERVICE}" ]
}

@test "countme: every binary the service executes is provided by an installed package" {
    # Extract the binary from each Exec* directive (strip modifiers like -, @, +).
    while IFS= read -r bin; do
        pkg="$(basename "${bin}")"
        run grep -Eq "^[[:space:]]*\"${pkg}\"," "${PKGS_TOML}"
        [ "$status" -eq 0 ] || {
            echo "package '${pkg}' (for ${bin} in bluefin-lts-countme.service) missing from [install] in base.toml"
            return 1
        }
    done < <(grep -E '^Exec' "${COUNTME_SERVICE}" | sed -E 's/^Exec[A-Za-z]*=[-@+!:]*//' | awk '{print $1}')
}

@test "countme: dnf5 is in the base install list" {
    grep -Eq '^[[:space:]]*"dnf5",' "${PKGS_TOML}"
}
