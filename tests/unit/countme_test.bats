#!/usr/bin/env bats

# Regression and feature tests for bluefin-lts-countme.service, timer, and helper script.
# The service runs `/usr/bin/dnf makecache` for EPEL reporting and
# `/usr/libexec/bluefin-lts-countme` for first-party reporting to countme.projectbluefin.io.
# Ref: projectbluefin/documentation ADR 0006, projectbluefin/bluefin-lts#591
# Run with: bats tests/unit/countme_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
PKGS_TOML="${SCRIPT_DIR}/../../build_scripts/packages/base.toml"
COUNTME_SERVICE="${SCRIPT_DIR}/../../system_files/usr/lib/systemd/system/bluefin-lts-countme.service"
COUNTME_TIMER="${SCRIPT_DIR}/../../system_files/usr/lib/systemd/system/bluefin-lts-countme.timer"
COUNTME_SCRIPT="${SCRIPT_DIR}/../../system_files/usr/libexec/bluefin-lts-countme"

# Binaries provided by the centos-bootc base image or repository system_files, not by base.toml.
BASE_IMAGE_BINARIES=("dnf" "bluefin-lts-countme")

setup() {
    TEST_ROOT="${BATS_TEST_TMPDIR}/countme-sandbox"
    STUB_BIN="${TEST_ROOT}/stub-bin"
    STATE_DIR="${TEST_ROOT}/var/lib/bluefin-lts-countme"
    CURL_LOG="${TEST_ROOT}/curl.log"

    mkdir -p "${STUB_BIN}" "${STATE_DIR}" "${TEST_ROOT}/usr/share/ublue-os" "${TEST_ROOT}/usr/lib"

    # Default curl stub: records invoked arguments and URL
    cat > "${STUB_BIN}/curl" <<EOF_STUB
#!/usr/bin/env bash
echo "\$@" >> "${CURL_LOG}"
exit 0
EOF_STUB
    chmod +x "${STUB_BIN}/curl"

    # Default image-info.json
    cat > "${TEST_ROOT}/usr/share/ublue-os/image-info.json" <<'EOF_INFO'
{
  "image-name": "bluefin",
  "image-flavor": "main",
  "image-tag": "stable",
  "centos-version": "10"
}
EOF_INFO

    # Default os-release
    cat > "${TEST_ROOT}/usr/lib/os-release" <<'EOF_OS'
NAME="Bluefin LTS"
VERSION_ID="10"
EOF_OS
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# Helper to run the countme script in sandbox environment
_run_countme() {
    run env \
        PATH="${STUB_BIN}:${PATH}" \
        DISABLED_FILE="${DISABLED_FILE:-${TEST_ROOT}/etc/projectbluefin/countme/disabled}" \
        LEGACY_DISABLED_FILE="${LEGACY_DISABLED_FILE:-${TEST_ROOT}/etc/dakota-countme/disabled}" \
        IMAGE_INFO="${IMAGE_INFO:-${TEST_ROOT}/usr/share/ublue-os/image-info.json}" \
        OS_RELEASE="${OS_RELEASE:-${TEST_ROOT}/usr/lib/os-release}" \
        STATE_DIR="${STATE_DIR:-${TEST_ROOT}/var/lib/bluefin-lts-countme}" \
        COUNTME_ENDPOINT="${COUNTME_ENDPOINT:-https://countme.projectbluefin.io/metalink}" \
        REPO="${REPO:-bluefin-lts}" \
        bash "${COUNTME_SCRIPT}"
}

@test "countme: service unit exists" {
    [ -f "${COUNTME_SERVICE}" ]
}

@test "countme: helper script exists and is executable" {
    [ -x "${COUNTME_SCRIPT}" ]
}

@test "countme: every binary the service executes is available in the image" {
    # Extract the binary from each Exec* directive (strip modifiers like -, @, +).
    while IFS= read -r bin; do
        pkg="$(basename "${bin}")"
        provided=1
        if [ -f "${SCRIPT_DIR}/../../system_files${bin}" ]; then
            provided=0
        fi
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

@test "countme: service executes first-party bluefin-lts-countme script" {
    grep -q '^ExecStart=/usr/libexec/bluefin-lts-countme' "${COUNTME_SERVICE}"
}

@test "countme: service and timer units honor opt-out via ConditionPathExists" {
    grep -Fx 'ConditionPathExists=!/etc/projectbluefin/countme/disabled' "${COUNTME_SERVICE}"
    grep -Fx 'ConditionPathExists=!/etc/projectbluefin/countme/disabled' "${COUNTME_TIMER}"
}

@test "countme: service unit configures StateDirectory" {
    grep -q '^StateDirectory=bluefin-lts-countme' "${COUNTME_SERVICE}"
}

@test "countme: script exits 0 and skips network call when opt-out marker exists" {
    mkdir -p "$(dirname "${TEST_ROOT}/etc/projectbluefin/countme/disabled")"
    touch "${TEST_ROOT}/etc/projectbluefin/countme/disabled"
    _run_countme
    [ "$status" -eq 0 ]
    [ ! -f "${CURL_LOG}" ]
}

@test "countme: script exits 0 and skips network call when legacy opt-out marker exists" {
    mkdir -p "$(dirname "${TEST_ROOT}/etc/dakota-countme/disabled")"
    touch "${TEST_ROOT}/etc/dakota-countme/disabled"
    _run_countme
    [ "$status" -eq 0 ]
    [ ! -f "${CURL_LOG}" ]
}

@test "countme: script safely skips when curl is unavailable" {
    NO_CURL_BIN="${TEST_ROOT}/no-curl-bin"
    mkdir -p "${NO_CURL_BIN}"
    for tool in /bin/* /usr/bin/*; do
        b="$(basename "$tool")"
        if [ "$b" != "curl" ] && [ -x "$tool" ] && [ ! -d "$tool" ]; then
            ln -sf "$tool" "${NO_CURL_BIN}/$b"
        fi
    done
    run env PATH="${NO_CURL_BIN}" /bin/bash "${COUNTME_SCRIPT}"
    [ "$status" -eq 0 ]
    [[ "$output" =~ "curl is unavailable; skipping telemetry" ]]
}

@test "countme: script safely skips when jq is unavailable" {
    NO_JQ_BIN="${TEST_ROOT}/no-jq-bin"
    mkdir -p "${NO_JQ_BIN}"
    for tool in /bin/* /usr/bin/*; do
        b="$(basename "$tool")"
        if [ "$b" != "jq" ] && [ -x "$tool" ] && [ ! -d "$tool" ]; then
            ln -sf "$tool" "${NO_JQ_BIN}/$b"
        fi
    done
    run env PATH="${NO_JQ_BIN}" /bin/bash "${COUNTME_SCRIPT}"
    [ "$status" -eq 0 ]
    [[ "$output" =~ "jq is unavailable; skipping telemetry" ]]
}

@test "countme: script computes bucket 1 on fresh install (< 7 days)" {
    _run_countme
    [ "$status" -eq 0 ]
    [ -f "${CURL_LOG}" ]
    grep -q "repo=bluefin-lts" "${CURL_LOG}"
    grep -q "countme=1" "${CURL_LOG}"
    grep -q "tag=stable" "${CURL_LOG}"
    grep -q "flavor=main" "${CURL_LOG}"
}

@test "countme: script computes bucket 2 for 2-4 weeks (7-27 days)" {
    now=$(date +%s)
    echo "$(( now - 14 * 86400 ))" > "${STATE_DIR}/epoch"
    _run_countme
    [ "$status" -eq 0 ]
    grep -q "countme=2" "${CURL_LOG}"
}

@test "countme: script computes bucket 3 for 5-24 weeks (28-167 days)" {
    now=$(date +%s)
    echo "$(( now - 35 * 86400 ))" > "${STATE_DIR}/epoch"
    _run_countme
    [ "$status" -eq 0 ]
    grep -q "countme=3" "${CURL_LOG}"
}

@test "countme: script computes bucket 4 for >24 weeks (168+ days)" {
    now=$(date +%s)
    echo "$(( now - 200 * 86400 ))" > "${STATE_DIR}/epoch"
    _run_countme
    [ "$status" -eq 0 ]
    grep -q "countme=4" "${CURL_LOG}"
}

@test "countme: script throttles repeated runs within 7 days" {
    _run_countme
    [ "$status" -eq 0 ]
    [ -f "${CURL_LOG}" ]
    [ -f "${STATE_DIR}/lastrun" ]

    rm -f "${CURL_LOG}"
    _run_countme
    [ "$status" -eq 0 ]
    [ ! -f "${CURL_LOG}" ]
}
