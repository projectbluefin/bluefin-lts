#!/usr/bin/env bats

# Regression tests for bluefin-lts-countme.service dependencies.
# The service runs `/usr/bin/dnf makecache`. dnf5 is uninstallable on CentOS
# Stream 10 (not in base/AppStream/CRB/EPEL, verified 2026-08-09), but the
# dnf CLI (dnf4) covers the job: it refreshes the EPEL metalink fine, fires
# the countme cookie, and reports User-Agent "Bluefin LTS 10" from os-release
# (verified against bluefin-lts:testing, 2026-08-09). The
# ${releasever_minor:+-z} failure in coreos/rpm-ostree#5464 is specific to
# rpm-ostree-countme's embedded libdnf4 usage, not the dnf CLI.
# Run with: bats tests/unit/countme_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
PKGS_TOML="${SCRIPT_DIR}/../../build_scripts/packages/base.toml"
COUNTME_SERVICE="${SCRIPT_DIR}/../../system_files/usr/lib/systemd/system/bluefin-lts-countme.service"

# Binaries provided by the centos-bootc base image, not by base.toml.
BASE_IMAGE_BINARIES=("dnf")

@test "countme: service unit exists" {
    [ -f "${COUNTME_SERVICE}" ]
}

@test "countme: every binary the service executes is available in the image" {
    # Extract the binary from each Exec* directive (strip modifiers like -, @, +).
    while IFS= read -r bin; do
        pkg="$(basename "${bin}")"
        provided=1
        for base_pkg in "${BASE_IMAGE_BINARIES[@]}"; do
            [ "${pkg}" = "${base_pkg}" ] && provided=0
        done
        if [ "${provided}" -ne 0 ]; then
            run grep -Eq "^[[:space:]]*\"${pkg}\"," "${PKGS_TOML}"
            [ "$status" -eq 0 ] || {
                echo "package '${pkg}' (for ${bin} in bluefin-lts-countme.service) missing from [install] in base.toml"
                return 1
            }
        fi
    done < <(grep -E '^Exec' "${COUNTME_SERVICE}" | sed -E 's/^Exec[A-Za-z]*=[-@+!:]*//' | awk '{print $1}')
}

@test "countme: service uses dnf, and dnf5 is not required from base.toml" {
    grep -q '^ExecStart=/usr/bin/dnf ' "${COUNTME_SERVICE}"
    # dnf5 is uninstallable on CS10 (verified 2026-08-09); adding it back to
    # base.toml kills the image build.
    ! grep -Eq '^[[:space:]]*"dnf5",' "${PKGS_TOML}"
}
