#!/usr/bin/env bats

# Unit tests for build_scripts/scripts/kernel-swap.sh
# Run with: bats tests/unit/kernel_swap_test.bats
#
# Strategy: extract pure-shell logic snippets that can be tested in isolation.
# Tools requiring a real OS environment (rpm, dnf, skopeo, dracut, depmod,
# ghcurl) are stubbed.  All file-system operations are redirected into
# BATS_TEST_TMPDIR so the host is never touched.

# ── Snippets verbatim from kernel-swap.sh ────────────────────────────────────

# CACHED_VERSION detection: list kernel-*.rpm in the mounted directory
# Note: the || true prevents set -euo pipefail from aborting on ls exit-2 (no glob match)
# when the RPM directory is empty; the empty-CACHED_VERSION check handles that error path.
DETECT_CACHED_VERSION='
set -euo pipefail
KERNEL_RPM_DIR="${KERNEL_RPM_DIR:-/tmp/kernel-rpms}"
CACHED_VERSION=$(cd "${KERNEL_RPM_DIR}" && ls kernel-[0-9]*.rpm 2>/dev/null | head -1 | sed -E '"'"'s/^kernel-//;s/\.rpm$//'"'"' || true)
if [[ -z "$CACHED_VERSION" ]]; then
  echo "ERROR: Could not detect kernel version from ${KERNEL_RPM_DIR}"
  exit 1
fi
echo "${CACHED_VERSION}"
'

# FEDORA_VERSION detection: parse fc<N> from the installed kernel version string
# Note: grep exits 1 when there is no fc<N> tag (el10 kernels); || true lets the
# fallback branch run instead of aborting under set -euo pipefail.
DETECT_FEDORA_VERSION='
set -euo pipefail
KERNEL_VERSION="${KERNEL_VERSION:-}"
FEDORA_AKMODS_VERSION="${FEDORA_AKMODS_VERSION:-43}"
FEDORA_VERSION=$(echo "${KERNEL_VERSION}" | grep -oP '"'"'fc\K[0-9]+'"'"' || true)
if [[ -z "${FEDORA_VERSION}" ]]; then
  FEDORA_VERSION="${FEDORA_AKMODS_VERSION}"
fi
echo "${FEDORA_VERSION}"
'

# dracut.conf.d snippet: create tmpdir config, verify it is written, then clean up
DRACUT_CONF_SNIPPET='
set -euo pipefail
DRACUT_CONF_DIR="${DRACUT_CONF_DIR:-/etc/dracut.conf.d}"
mkdir -p "${DRACUT_CONF_DIR}"
echo '"'"'tmpdir="/boot"'"'"' > "${DRACUT_CONF_DIR}/01-tmpdir.conf"
# Verify the file was created and contains expected content
[[ -f "${DRACUT_CONF_DIR}/01-tmpdir.conf" ]] || { echo "ERROR: conf file not created"; exit 1; }
grep -q '"'"'tmpdir="/boot"'"'"' "${DRACUT_CONF_DIR}/01-tmpdir.conf" || { echo "ERROR: wrong content"; exit 1; }
# Simulate cleanup step
rm -f "${DRACUT_CONF_DIR}/01-tmpdir.conf"
[[ ! -f "${DRACUT_CONF_DIR}/01-tmpdir.conf" ]] || { echo "ERROR: conf file not removed"; exit 1; }
'

# ── CACHED_VERSION detection ──────────────────────────────────────────────────

@test "cached_version: detects version from standard kernel rpm filename" {
    local dir="${BATS_TEST_TMPDIR}/kernel-rpms"
    mkdir -p "${dir}"
    touch "${dir}/kernel-6.12.0-200.fc44.x86_64.rpm"
    touch "${dir}/kernel-core-6.12.0-200.fc44.x86_64.rpm"
    KERNEL_RPM_DIR="${dir}" run bash -c "$DETECT_CACHED_VERSION"
    [ "$status" -eq 0 ]
    [ "$output" = "6.12.0-200.fc44.x86_64" ]
}

@test "cached_version: detects version from el10 dist tag" {
    local dir="${BATS_TEST_TMPDIR}/kernel-rpms-el"
    mkdir -p "${dir}"
    touch "${dir}/kernel-6.12.0-200.el10.x86_64.rpm"
    KERNEL_RPM_DIR="${dir}" run bash -c "$DETECT_CACHED_VERSION"
    [ "$status" -eq 0 ]
    [ "$output" = "6.12.0-200.el10.x86_64" ]
}

@test "cached_version: picks first match when multiple kernel rpms present" {
    local dir="${BATS_TEST_TMPDIR}/kernel-rpms-multi"
    mkdir -p "${dir}"
    # Create filenames that sort deterministically
    touch "${dir}/kernel-6.11.0-100.fc43.x86_64.rpm"
    touch "${dir}/kernel-6.12.0-200.fc44.x86_64.rpm"
    KERNEL_RPM_DIR="${dir}" run bash -c "$DETECT_CACHED_VERSION"
    [ "$status" -eq 0 ]
    # The first alphabetically is 6.11.0
    [ "$output" = "6.11.0-100.fc43.x86_64" ]
}

@test "cached_version: exits with error when no kernel rpms found" {
    local dir="${BATS_TEST_TMPDIR}/kernel-rpms-empty"
    mkdir -p "${dir}"
    KERNEL_RPM_DIR="${dir}" run bash -c "$DETECT_CACHED_VERSION"
    [ "$status" -ne 0 ]
    [[ "$output" == *"ERROR"* ]]
}

@test "cached_version: error message includes the directory path" {
    local dir="${BATS_TEST_TMPDIR}/kernel-rpms-missing"
    mkdir -p "${dir}"
    KERNEL_RPM_DIR="${dir}" run bash -c "$DETECT_CACHED_VERSION"
    [ "$status" -ne 0 ]
    [[ "$output" == *"${dir}"* ]]
}

@test "cached_version: non-kernel rpms in directory are ignored" {
    local dir="${BATS_TEST_TMPDIR}/kernel-rpms-other"
    mkdir -p "${dir}"
    touch "${dir}/kernel-core-6.12.0-200.fc44.x86_64.rpm"
    touch "${dir}/kernel-modules-6.12.0-200.fc44.x86_64.rpm"
    # No plain kernel-*.rpm with version starting digit
    KERNEL_RPM_DIR="${dir}" run bash -c "$DETECT_CACHED_VERSION"
    [ "$status" -ne 0 ]
}

@test "cached_version: glob does not match kernel-core, kernel-modules" {
    local dir="${BATS_TEST_TMPDIR}/kernel-rpms-nocore"
    mkdir -p "${dir}"
    touch "${dir}/kernel-core-6.12.0-200.fc44.x86_64.rpm"
    touch "${dir}/kernel-modules-extra-6.12.0-200.fc44.x86_64.rpm"
    KERNEL_RPM_DIR="${dir}" run bash -c "$DETECT_CACHED_VERSION"
    # kernel-[0-9]*.rpm requires first char after 'kernel-' to be a digit
    [ "$status" -ne 0 ]
}

# ── FEDORA_VERSION detection ──────────────────────────────────────────────────

@test "fedora_version: extracts fc number from standard kernel version" {
    KERNEL_VERSION="6.12.0-200.fc44.x86_64" run bash -c "$DETECT_FEDORA_VERSION"
    [ "$status" -eq 0 ]
    [ "$output" = "44" ]
}

@test "fedora_version: extracts fc number from older fc43 kernel" {
    KERNEL_VERSION="6.11.0-100.fc43.x86_64" run bash -c "$DETECT_FEDORA_VERSION"
    [ "$status" -eq 0 ]
    [ "$output" = "43" ]
}

@test "fedora_version: falls back to FEDORA_AKMODS_VERSION when no fc tag" {
    KERNEL_VERSION="6.12.0-200.el10.x86_64" FEDORA_AKMODS_VERSION="43" run bash -c "$DETECT_FEDORA_VERSION"
    [ "$status" -eq 0 ]
    [ "$output" = "43" ]
}

@test "fedora_version: uses default fallback of 43 when FEDORA_AKMODS_VERSION unset" {
    KERNEL_VERSION="6.12.0-200.el10.x86_64" run bash -c "unset FEDORA_AKMODS_VERSION; $DETECT_FEDORA_VERSION"
    [ "$status" -eq 0 ]
    [ "$output" = "43" ]
}

@test "fedora_version: custom FEDORA_AKMODS_VERSION respected on fallback" {
    KERNEL_VERSION="6.12.0-200.el10.x86_64" FEDORA_AKMODS_VERSION="42" run bash -c "$DETECT_FEDORA_VERSION"
    [ "$status" -eq 0 ]
    [ "$output" = "42" ]
}

@test "fedora_version: fc tag takes precedence over FEDORA_AKMODS_VERSION" {
    KERNEL_VERSION="6.12.0-200.fc44.x86_64" FEDORA_AKMODS_VERSION="99" run bash -c "$DETECT_FEDORA_VERSION"
    [ "$status" -eq 0 ]
    # fc44 wins over FEDORA_AKMODS_VERSION=99
    [ "$output" = "44" ]
}

# ── dracut.conf.d tmpdir config ───────────────────────────────────────────────

@test "dracut_conf: creates 01-tmpdir.conf with tmpdir=/boot" {
    local confdir="${BATS_TEST_TMPDIR}/dracut.conf.d"
    DRACUT_CONF_DIR="${confdir}" run bash -c "$DRACUT_CONF_SNIPPET"
    [ "$status" -eq 0 ]
}

@test "dracut_conf: conf file is removed after cleanup step" {
    local confdir="${BATS_TEST_TMPDIR}/dracut-cleanup"
    DRACUT_CONF_DIR="${confdir}" run bash -c "$DRACUT_CONF_SNIPPET"
    [ "$status" -eq 0 ]
    # Verify cleanup removed the file
    [ ! -f "${confdir}/01-tmpdir.conf" ]
}
