#!/usr/bin/env bats

# Static tests for the Vicinae block in build_scripts/21-build-gnome-extensions.sh.
# The two Dakota-port build breaks (missing /tmp/vicinae; x86_64-only asset breaking
# the aarch64 build) are not caught by shellcheck or `bash -n`, so assert on the
# script structure directly.
# Run with: bats tests/unit/gnome_extensions_dakota_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD="${REPO_ROOT}/build_scripts/21-build-gnome-extensions.sh"

setup() {
    [ -f "${BUILD}" ] || skip "21-build-gnome-extensions.sh not found"
}

# Fix #1: /tmp/vicinae must be created before it is used as a tar extraction target.
test vicinae_directory_created_before_tar_extraction() {
    mkdir_line=$(grep -n 'mkdir -p /tmp/vicinae' "${BUILD}" | head -1 | cut -d: -f1)
    tar_line=$(grep -n 'tar -xzf /tmp/vicinae.tar.gz -C /tmp/vicinae' "${BUILD}" | head -1 | cut -d: -f1)
    [ -n "${mkdir_line}" ] || { echo "FAIL: no 'mkdir -p /tmp/vicinae' in ${BUILD}"; return 1; }
    [ -n "${tar_line}" ]  || { echo "FAIL: no 'tar -xzf ... -C /tmp/vicinae' in ${BUILD}"; return 1; }
    [ "${mkdir_line}" -lt "${tar_line}" ] || { echo "FAIL: mkdir (mkdir_line) is not before tar (tar_line)"; return 1; }
}

# Fix #2: the Vicinae block must be guarded behind an aarch64 check, since upstream
# ships no aarch64/arm64 build and curl -fsSL would 404 and abort the build.
test vicinae_block_is_arch_guarded() {
    guard_line=$(grep -n 'if \[ "\$ARCH" != "aarch64" \]' "${BUILD}" | head -1 | cut -d: -f1)
    tar_line=$(grep -n 'tar -xzf /tmp/vicinae.tar.gz -C /tmp/vicinae' "${BUILD}" | head -1 | cut -d: -f1)
    [ -n "${guard_line}" ] || { echo "FAIL: no aarch64 guard 'if [ \"\$ARCH\" != \"aarch64\" ]'"; return 1; }
    [ -n "${tar_line}" ]   || { echo "FAIL: no Vicinae tar extraction line"; return 1; }
    # The tar line must be indented (inside the if block), not at column 0.
    tar_content=$(sed -n "${tar_line}p" "${BUILD}")
    case "${tar_content}" in
        ' '*|'	'*) : ;;  # indented -> inside the guard
        *) echo "FAIL: Vicinae tar line is not inside the aarch64 guard"; return 1 ;;
    esac
    [ "${guard_line}" -lt "${tar_line}" ] || { echo "FAIL: guard is not before the Vicinae block"; return 1; }
}

# Regression: the aarch64 guard must not wrap Quick Settings Audio Panel, which
# ships for both architectures.
test qsap_is_not_arch_guarded() {
    qsap_zip=$(grep -n 'quick-settings-audio-panel.*shell-extension.zip' "${BUILD}" | head -1 | cut -d: -f1)
    guard_line=$(grep -n 'if \[ "\$ARCH" != "aarch64" \]' "${BUILD}" | head -1 | cut -d: -f1)
    [ -n "${qsap_zip}" ] || { echo "FAIL: QSAP download line missing"; return 1; }
    [ -n "${guard_line}" ] || return 0
    # If the guard precedes the QSAP line, that would be a regression.
    [ "${guard_line}" -lt "${qsap_zip}" ] || return 0
    echo "FAIL: QSAP download is incorrectly wrapped in the aarch64 guard"
    return 1
}
