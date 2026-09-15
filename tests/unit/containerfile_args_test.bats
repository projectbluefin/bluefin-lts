#!/usr/bin/env bats
#
# Guard for the base-image identity axis in the Containerfile.
#
# Filed against projectbluefin/bluefin-lts#559: the base image was stated four
# times with two different values and pinned by nothing. Phase 1 of that finding
# deletes the ARG declarations that provably reach no consumer and adds this
# guard so the *next* dead declaration fails CI instead of silently accumulating.
#
# Two invariants are enforced here:
#   1. Every `ARG` in the Containerfile has a consumer: it is interpolated in the
#      Containerfile (outside its own declaration line) OR passed as a --build-arg
#      by the Justfile.
#   2. `MAJOR_VERSION` is never given conflicting default values across its
#      declarations.
#
# Run with: bats tests/unit/containerfile_args_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
CONTAINERFILE="${SCRIPT_DIR}/../../Containerfile"
JUSTFILE="${SCRIPT_DIR}/../../Justfile"

setup() {
    [ -f "${CONTAINERFILE}" ]
    [ -f "${JUSTFILE}" ]
}

# ──────────────────────────────────────────────────────────────────────────────
# consumers: every ARG name that is actually used somewhere
# ──────────────────────────────────────────────────────────────────────────────

# ARG names declared in the Containerfile.
_arg_names() {
    grep -oE '^[[:space:]]*ARG[[:space:]]+[A-Za-z_][A-Za-z0-9_]*' "${CONTAINERFILE}" \
        | awk '{print $2}' | sort -u
}

# ARG names interpolated in the Containerfile, excluding the declaration lines
# themselves (an `ARG X="${X:-...}"` line must not count as X's own consumer).
_container_consumers() {
    grep -vE '^[[:space:]]*ARG[[:space:]]+' "${CONTAINERFILE}" \
        | grep -oE '\$\{?[A-Za-z_][A-Za-z0-9_]*' \
        | sed -E 's/^\$\{?//' | sort -u
}

# ARG names the Justfile passes as build arguments. The Justfile writes these as
# `--build-arg" "NAME=..."`, so the pattern spans the quote + space + quote.
_justfile_consumers() {
    grep -oE -- '--build-arg" "[A-Za-z_][A-Za-z0-9_]*' "${JUSTFILE}" \
        | sed -E 's/--build-arg" "//; s/"$//' | sort -u
}

# All consumers combined.
_all_consumers() {
    { _container_consumers; _justfile_consumers; } | sort -u
}

# ──────────────────────────────────────────────────────────────────────────────
# every ARG has a consumer
# ──────────────────────────────────────────────────────────────────────────────

@test "containerfile: every ARG has a consumer" {
    consumers="$(_all_consumers)"
    failed=0
    for name in "$(_arg_names)"; do
        if ! printf '%s\n' "${consumers}" | grep -qxF "${name}"; then
            echo "ARG ${name} has no consumer (not interpolated in the Containerfile and not passed by the Justfile)"
            failed=1
        fi
    done
    [ "${failed}" -eq 0 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# MAJOR_VERSION defaults never conflict
# ──────────────────────────────────────────────────────────────────────────────

# Distinct default values across every `ARG MAJOR_VERSION=...` declaration.
_major_version_defaults() {
    grep -E '^[[:space:]]*ARG[[:space:]]+MAJOR_VERSION=' "${CONTAINERFILE}" \
        | grep -oE ':-[A-Za-z0-9._-]+' | sed -E 's/^://' | sort -u
}

@test "containerfile: MAJOR_VERSION has a single consistent default" {
    distinct="$(_major_version_defaults)"
    count=$(printf '%s\n' "${distinct}" | grep -c .)
    [ "${count}" -le 1 ]
}

# ──────────────────────────────────────────────────────────────────────────────
# Phase 1 fixes are in place (lock in the deletions from #559)
# ──────────────────────────────────────────────────────────────────────────────

@test "containerfile: dead BASE_IMAGE_SHA declaration is removed" {
    run grep -c 'ARG BASE_IMAGE_SHA' "${CONTAINERFILE}"
    [ "${status}" -ne 0 ]
}

@test "containerfile: post-FROM MAJOR_VERSION lts default is removed" {
    run grep -q 'MAJOR_VERSION:-lts' "${CONTAINERFILE}"
    [ "${status}" -ne 0 ]
}
