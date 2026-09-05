#!/usr/bin/env bats

# Unit tests for build_scripts/scripts/ghcurl
#
# ghcurl is the wrapper every build script uses to fetch GitHub release assets
# (uupd, uupd.service, offline documentation, ...). If it silently stops
# retrying, drops caller options, or swallows a curl failure, the build ships an
# image with a missing or truncated asset. image_info_test.bats stubs ghcurl
# away entirely, so nothing exercised the wrapper itself until now.
#
# The authenticated branch reads a fixed path (/run/secrets/GITHUB_TOKEN) that a
# test cannot create, so those tests are skip-guarded and only run where the
# Podman secret is actually mounted.
#
# Run with: bats tests/unit/ghcurl_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
GHCURL="${SCRIPT_DIR}/../../build_scripts/scripts/ghcurl"
TOKEN_SECRET="/run/secrets/GITHUB_TOKEN"

setup() {
    STUB_BIN="${BATS_TEST_TMPDIR}/stub-bin"
    CURL_LOG="${BATS_TEST_TMPDIR}/curl-args"
    mkdir -p "${STUB_BIN}"

    # Stub curl: record argv one-per-line, echo a marker, honour STUB_CURL_EXIT.
    cat > "${STUB_BIN}/curl" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" > "${CURL_LOG}"
echo "STUB_CURL_OUTPUT"
exit "\${STUB_CURL_EXIT:-0}"
EOF
    chmod +x "${STUB_BIN}/curl"
}

run_ghcurl() {
    PATH="${STUB_BIN}:${PATH}" run bash "${GHCURL}" "$@"
}

# Fails the test unless the stub recorded the exact argument.
assert_curl_arg() {
    grep -Fxq -- "$1" "${CURL_LOG}"
}

skip_if_token_mounted() {
    if [[ -f "${TOKEN_SECRET}" ]]; then
        skip "a real ${TOKEN_SECRET} is mounted; unauthenticated branch not reachable"
    fi
}

@test "ghcurl: script exists and is executable" {
    [ -x "${GHCURL}" ]
}

@test "ghcurl: passes the URL through to curl" {
    skip_if_token_mounted
    run_ghcurl "https://example.invalid/asset.tar.gz"
    [ "$status" -eq 0 ]
    assert_curl_arg "https://example.invalid/asset.tar.gz"
}

@test "ghcurl: the URL is the final curl argument" {
    skip_if_token_mounted
    run_ghcurl "https://example.invalid/asset" --retry 3 -Lo /tmp/asset
    [ "$status" -eq 0 ]
    [ "$(tail -n 1 "${CURL_LOG}")" = "https://example.invalid/asset" ]
}

@test "ghcurl: always requests silent, show-error, follow-redirects" {
    skip_if_token_mounted
    run_ghcurl "https://example.invalid/asset"
    [ "$status" -eq 0 ]
    assert_curl_arg "-sSL"
}

@test "ghcurl: forwards caller options after the URL argument" {
    skip_if_token_mounted
    run_ghcurl "https://example.invalid/asset" --retry 3 -Lo /tmp/out.pdf
    [ "$status" -eq 0 ]
    assert_curl_arg "--retry"
    assert_curl_arg "3"
    assert_curl_arg "-Lo"
    assert_curl_arg "/tmp/out.pdf"
}

@test "ghcurl: preserves the order of caller options" {
    skip_if_token_mounted
    run_ghcurl "https://example.invalid/asset" --retry 3 -Lo /tmp/out.pdf
    [ "$status" -eq 0 ]
    [ "$(grep -c . "${CURL_LOG}")" -eq 6 ]
    [ "$(sed -n '1p' "${CURL_LOG}")" = "-sSL" ]
    [ "$(sed -n '2p' "${CURL_LOG}")" = "--retry" ]
    [ "$(sed -n '3p' "${CURL_LOG}")" = "3" ]
    [ "$(sed -n '4p' "${CURL_LOG}")" = "-Lo" ]
    [ "$(sed -n '5p' "${CURL_LOG}")" = "/tmp/out.pdf" ]
}

@test "ghcurl: options containing spaces stay a single argument" {
    skip_if_token_mounted
    run_ghcurl "https://example.invalid/asset" -o "/tmp/two words.pdf"
    [ "$status" -eq 0 ]
    assert_curl_arg "/tmp/two words.pdf"
}

@test "ghcurl: works with no options beyond the URL" {
    skip_if_token_mounted
    run_ghcurl "https://example.invalid/asset"
    [ "$status" -eq 0 ]
    [ "$(grep -c . "${CURL_LOG}")" -eq 2 ]
}

@test "ghcurl: relays curl stdout to the caller" {
    skip_if_token_mounted
    run_ghcurl "https://example.invalid/asset"
    [ "$status" -eq 0 ]
    [[ "$output" == *"STUB_CURL_OUTPUT"* ]]
}

@test "ghcurl: propagates a curl failure exit code" {
    skip_if_token_mounted
    STUB_CURL_EXIT=22 run_ghcurl "https://example.invalid/missing"
    [ "$status" -eq 22 ]
}

@test "ghcurl: reports the missing token secret on stderr, not stdout" {
    skip_if_token_mounted
    PATH="${STUB_BIN}:${PATH}" run bash -c \
        "bash '${GHCURL}' https://example.invalid/asset 2>/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" != *"GITHUB_TOKEN"* ]]

    PATH="${STUB_BIN}:${PATH}" run bash -c \
        "bash '${GHCURL}' https://example.invalid/asset 2>&1 >/dev/null"
    [ "$status" -eq 0 ]
    [[ "$output" == *"GITHUB_TOKEN secret not found"* ]]
}

@test "ghcurl: sends no Authorization header when the token secret is absent" {
    skip_if_token_mounted
    run_ghcurl "https://example.invalid/asset"
    [ "$status" -eq 0 ]
    ! grep -qi "Authorization" "${CURL_LOG}"
    ! grep -Fxq -- "-H" "${CURL_LOG}"
}

@test "ghcurl: fails when called without a URL" {
    skip_if_token_mounted
    PATH="${STUB_BIN}:${PATH}" run bash "${GHCURL}"
    [ "$status" -ne 0 ]
    [ ! -f "${CURL_LOG}" ]
}

@test "ghcurl: sends an Authorization header when the token secret is mounted" {
    if [[ ! -f "${TOKEN_SECRET}" ]]; then
        skip "no ${TOKEN_SECRET} mounted; authenticated branch not reachable"
    fi
    run_ghcurl "https://example.invalid/asset"
    [ "$status" -eq 0 ]
    assert_curl_arg "-H"
    grep -qi "^Authorization: " "${CURL_LOG}"
}
