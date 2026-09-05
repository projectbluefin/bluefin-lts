#!/usr/bin/env bats

# Unit tests for the Containerfile build-arg contract.
#
# Every ARG in the Containerfile is an interface: it is either consumed by the
# Containerfile itself (interpolated into a FROM/COPY/RUN) or handed to the
# build payload under build_scripts/ and system_files/. An ARG that reaches
# neither is dead, and a dead ARG carrying a literal digest or version reads to
# a maintainer as if it were load-bearing. These tests fail when a declaration
# stops reaching a consumer, or when one name is given conflicting defaults.
#
# Run with: bats tests/unit/containerfile_args_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONTAINERFILE="${REPO_ROOT}/Containerfile"

# Names declared by `ARG <name>` in the Containerfile, deduplicated.
arg_names() {
    grep -E '^ARG[[:space:]]+[A-Za-z_][A-Za-z0-9_]*' "${CONTAINERFILE}" |
        sed -E 's/^ARG[[:space:]]+([A-Za-z_][A-Za-z0-9_]*).*/\1/' |
        sort -u
}

# Every `${NAME...}` / `$NAME` expansion in the Containerfile that is NOT the
# self-reference inside that name's own default (`ARG X="${X:-...}"`).
containerfile_expansions() {
    grep -vE '^ARG[[:space:]]' "${CONTAINERFILE}" |
        grep -oE '\$\{?[A-Za-z_][A-Za-z0-9_]*' |
        sed -E 's/^\$\{?//' |
        sort -u
}

# Names referenced anywhere in the build payload the RUN step executes.
payload_references() {
    grep -rhoE '\b[A-Z_][A-Z0-9_]*\b' \
        "${REPO_ROOT}/build_scripts" "${REPO_ROOT}/system_files" 2>/dev/null |
        sort -u
}

setup() {
    [ -f "${CONTAINERFILE}" ] || {
        echo "Containerfile not found at ${CONTAINERFILE}" >&2
        return 1
    }
}

# Known dead ARGs that cannot be removed here without also editing a consumer
# outside this change set. Tracked in issue #559; this list must only shrink.
#
#   GNOME_VERSION - passed by Justfile:130 but read by no build script; the
#                   GNOME stream is hardcoded in the COPR URL at
#                   build_scripts/overrides/base/10-packages-image-base.sh:24.
#                   Removing the ARG alone would leave the Justfile passing an
#                   undeclared build-arg, so both sides must move together.
KNOWN_DEAD_ARGS="GNOME_VERSION"

@test "Containerfile declares at least one ARG (guard is not vacuous)" {
    run bash -c "$(declare -f arg_names); CONTAINERFILE='${CONTAINERFILE}'; arg_names | wc -l"
    [ "$status" -eq 0 ]
    [ "$output" -gt 0 ]
}

@test "every ARG in the Containerfile reaches a consumer" {
    local expansions payload dead=""
    expansions="$(containerfile_expansions)"
    payload="$(payload_references)"

    for name in $(arg_names); do
        if grep -qxF "${name}" <<<"${expansions}"; then
            continue
        fi
        if grep -qxF "${name}" <<<"${payload}"; then
            continue
        fi
        if grep -qw "${name}" <<<"${KNOWN_DEAD_ARGS}"; then
            continue
        fi
        dead+=" ${name}"
    done

    if [ -n "${dead}" ]; then
        echo "Dead Containerfile ARG(s):${dead}" >&2
        echo "Each is neither interpolated in the Containerfile nor referenced" >&2
        echo "under build_scripts/ or system_files/. Remove it, or wire it up." >&2
        return 1
    fi
}

@test "the known-dead ARG allowlist is not stale" {
    # If an allowlisted ARG gains a consumer or is deleted, it must leave the
    # list, otherwise the list silently grants a future dead ARG a free pass.
    local expansions payload stale=""
    expansions="$(containerfile_expansions)"
    payload="$(payload_references)"

    for name in ${KNOWN_DEAD_ARGS}; do
        if ! grep -qxF "${name}" <<<"$(arg_names)"; then
            stale+=" ${name}(no longer declared)"
        elif grep -qxF "${name}" <<<"${expansions}" ||
            grep -qxF "${name}" <<<"${payload}"; then
            stale+=" ${name}(now consumed)"
        fi
    done

    if [ -n "${stale}" ]; then
        echo "Remove from KNOWN_DEAD_ARGS:${stale}" >&2
        return 1
    fi
}

@test "BASE_IMAGE_SHA is not reintroduced without a consumer" {    # It existed as a frozen sha256 literal that nothing read, which made the
    # CentOS base look digest-pinned when it is resolved by mutable tag.
    if grep -qw 'BASE_IMAGE_SHA' "${CONTAINERFILE}"; then
        run grep -rqw 'BASE_IMAGE_SHA' "${REPO_ROOT}/build_scripts" "${REPO_ROOT}/Justfile"
        [ "$status" -eq 0 ]
    fi
}

@test "MAJOR_VERSION is never declared with conflicting defaults" {
    local defaults
    defaults="$(grep -E '^ARG[[:space:]]+MAJOR_VERSION' "${CONTAINERFILE}" |
        sed -E 's/^ARG[[:space:]]+MAJOR_VERSION=?//' | sort -u)"

    [ -n "${defaults}" ]
    [ "$(wc -l <<<"${defaults}")" -eq 1 ]
}

@test "MAJOR_VERSION is in scope for the base FROM that interpolates it" {
    # A global ARG only reaches a FROM if it is declared before that FROM.
    local from_line decl_line
    from_line="$(grep -nE '^FROM .*\$\{?MAJOR_VERSION' "${CONTAINERFILE}" |
        head -1 | cut -d: -f1)"
    [ -n "${from_line}" ]

    decl_line="$(grep -nE '^ARG[[:space:]]+MAJOR_VERSION' "${CONTAINERFILE}" |
        head -1 | cut -d: -f1)"
    [ -n "${decl_line}" ]
    [ "${decl_line}" -lt "${from_line}" ]
}

@test "the base image tag comes from MAJOR_VERSION, not a hardcoded tag" {
    run grep -cE '^FROM quay\.io/centos-bootc/centos-bootc:\$\{?MAJOR_VERSION' \
        "${CONTAINERFILE}"
    [ "$status" -eq 0 ]
    [ "$output" -eq 1 ]
}

@test "ARGs the Justfile passes are declared in the Containerfile" {
    local declared missing=""
    declared="$(arg_names)"

    while read -r name; do
        [ -n "${name}" ] || continue
        grep -qxF "${name}" <<<"${declared}" || missing+=" ${name}"
    done < <(grep -oE '\-\-build-arg" "[A-Z_][A-Z0-9_]*=' "${REPO_ROOT}/Justfile" |
        sed -E 's/.*"([A-Z_][A-Z0-9_]*)=/\1/' | sort -u)

    if [ -n "${missing}" ]; then
        echo "Justfile passes --build-arg for undeclared name(s):${missing}" >&2
        return 1
    fi
}
