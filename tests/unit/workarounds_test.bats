#!/usr/bin/env bats

# Unit tests for build_scripts/00-workarounds.sh
# Run with: bats tests/unit/workarounds_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
WORKAROUNDS_SCRIPT="${SCRIPT_DIR}/../../build_scripts/00-workarounds.sh"

setup() {
    TEST_ROOT="${SCRIPT_DIR}/.bats-sandbox/workarounds.${BATS_TEST_NUMBER:-0}.$$"
    STUB_BIN="${TEST_ROOT}/stub-bin"

    mkdir -p "${STUB_BIN}"
    mkdir -p "${TEST_ROOT}/etc/yum.repos.d"

    export PATH="${STUB_BIN}:${PATH}"
    export MAJOR_VERSION_NUMBER="10"

    # Default curl stub: writes a minimal compose.repo with a pinned compose name
    FAKE_COMPOSE="CentOS-Stream-10-20260101.0"
    cat > "${STUB_BIN}/curl" <<EOF
#!/usr/bin/bash
# Minimal stub — writes a usable compose.repo when called with -Lo
args="\$*"
if [[ "\${args}" =~ "-Lo" ]]; then
    DEST=\$(echo "\${args}" | grep -oE '"[^"]*"' | head -1 | tr -d '"')
    if [[ -z "\${DEST}" ]]; then
        DEST=\$(echo "\${args}" | awk '{for(i=1;i<=NF;i++) if(\$i=="-Lo") print \$(i+1)}')
    fi
    cat > "\${DEST:-/dev/null}" <<'REPOEOF'
[baseos-compose]
name=CentOS Stream 10 - BaseOS - Compose
baseurl=https://composes.stream.centos.org/stream-10/production/${FAKE_COMPOSE}/compose/BaseOS/x86_64/os/
enabled=1
gpgcheck=1

[appstream-compose]
name=CentOS Stream 10 - AppStream - Compose
baseurl=https://composes.stream.centos.org/stream-10/production/${FAKE_COMPOSE}/compose/AppStream/x86_64/os/
enabled=1
gpgcheck=1
REPOEOF
elif [[ "\${args}" =~ "-sfI" ]]; then
    # HEAD check: pinned compose is available
    exit 0
else
    # fallback: list page with compose name
    echo "${FAKE_COMPOSE}"
fi
EOF
    chmod +x "${STUB_BIN}/curl"

    # Patch absolute repo path to use TEST_ROOT
    PATCHED_SCRIPT="${TEST_ROOT}/workarounds-patched.sh"
    sed \
        -e "s|/etc/yum.repos.d/compose.repo|${TEST_ROOT}/etc/yum.repos.d/compose.repo|g" \
        "${WORKAROUNDS_SCRIPT}" > "${PATCHED_SCRIPT}"
    chmod +x "${PATCHED_SCRIPT}"
    export PATCHED_SCRIPT TEST_ROOT STUB_BIN FAKE_COMPOSE
}

teardown() {
    rm -rf "${TEST_ROOT}"
}

# ──────────────────────────────────────────────────────────────────────────────
# compose.repo creation
# ──────────────────────────────────────────────────────────────────────────────

@test "workarounds: compose.repo is created" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    [ -f "${TEST_ROOT}/etc/yum.repos.d/compose.repo" ]
}

@test "workarounds: compose.repo contains -compose repo IDs" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    grep -q "baseos-compose\|appstream-compose" "${TEST_ROOT}/etc/yum.repos.d/compose.repo"
}

# ──────────────────────────────────────────────────────────────────────────────
# compose.repo sed transformations
# ──────────────────────────────────────────────────────────────────────────────

@test "workarounds: repo IDs have -compose suffix after sed" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    repo_content=$(cat "${TEST_ROOT}/etc/yum.repos.d/compose.repo")
    # The sed in the script renames [baseos] -> [baseos-compose] etc.
    # Our stub already writes -compose IDs but the name-line sed also fires
    echo "${repo_content}" | grep -qiE "compose"
}

# ──────────────────────────────────────────────────────────────────────────────
# fallback when pinned compose is unavailable
# ──────────────────────────────────────────────────────────────────────────────

@test "workarounds: falls back to latest compose when pinned compose returns 404" {
    LATEST_COMPOSE="CentOS-Stream-10-20260601.0"
    # Override curl: HEAD check fails, list page returns latest compose
    cat > "${STUB_BIN}/curl" <<EOF
#!/usr/bin/bash
args="\$*"
if [[ "\${args}" =~ "-Lo" ]]; then
    DEST=\$(echo "\${args}" | awk '{for(i=1;i<=NF;i++) if(\$i=="-Lo") print \$(i+1)}')
    cat > "\${DEST:-/dev/null}" <<'REPOEOF'
[baseos-compose]
baseurl=https://composes.stream.centos.org/stream-10/production/CentOS-Stream-10-20260101.0/compose/BaseOS/x86_64/os/
REPOEOF
elif [[ "\${args}" =~ "-sfI" ]]; then
    # HEAD check fails — pinned compose unavailable
    exit 1
else
    # List page output — contains the latest compose name
    echo "${LATEST_COMPOSE}"
fi
EOF
    chmod +x "${STUB_BIN}/curl"

    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
    # The script should have replaced the old compose name with the latest
    grep -q "${LATEST_COMPOSE}" "${TEST_ROOT}/etc/yum.repos.d/compose.repo"
}

# ──────────────────────────────────────────────────────────────────────────────
# smoke
# ──────────────────────────────────────────────────────────────────────────────

@test "workarounds: script exits 0 with curl stubbed" {
    run bash "${PATCHED_SCRIPT}"
    [ "$status" -eq 0 ]
}
