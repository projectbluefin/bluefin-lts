#!/usr/bin/env bats

# Contract tests for the variant override dispatch in build_scripts/build.sh.
#
# build.sh drives two override trees that are keyed on the same (arch, variant)
# axis but use different path grammars:
#
#   system_files_overrides/<variant>            build_scripts/overrides/<variant>
#   system_files_overrides/<arch>               build_scripts/overrides/<arch>
#   system_files_overrides/<arch>-<variant>     build_scripts/overrides/<arch>/<variant>
#
# Both copy_systemfiles_for and run_buildscripts_for abort the image build when
# their directory is missing, so a half-declared variant only fails deep inside
# a container build. These tests pull the arch matrix from build-regular.yml and
# the variant list from build.sh and assert both trees agree, in both
# directions, at unit-test time.
#
# Run with: bats tests/unit/build_dispatch_test.bats

REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
BUILD_SCRIPT="${REPO_ROOT}/build_scripts/build.sh"
BUILD_WORKFLOW="${REPO_ROOT}/.github/workflows/build-regular.yml"
SCRIPT_OVERRIDES="${REPO_ROOT}/build_scripts/overrides"
FILE_OVERRIDES="${REPO_ROOT}/system_files_overrides"

# Directories under build_scripts/overrides that are neither an arch nor a
# variant root. "base" is dispatched unconditionally by build.sh.
NON_VARIANT_SCRIPT_DIRS="base"

supported_arches() {
    # Matches: architecture: '["x86_64", "aarch64"]'
    grep -oE "architecture: *'\[[^]]*\]'" "${BUILD_WORKFLOW}" |
        head -1 |
        grep -oE '"[^"]+"' |
        tr -d '"'
}

dispatched_variants() {
    grep -oE '^[[:space:]]*apply_variant[[:space:]]+[a-z0-9_-]+' "${BUILD_SCRIPT}" |
        awk '{print $2}' |
        sort -u
}

subdirs_of() {
    find "$1" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort
}

contains() {
    local needle="$1"
    shift
    local item
    for item in "$@"; do
        [ "${item}" = "${needle}" ] && return 0
    done
    return 1
}

require_dir() {
    if [ ! -d "$1" ]; then
        echo "missing required override directory: $1" >&2
        return 1
    fi
}

@test "build-regular.yml declares a parseable architecture matrix" {
    run supported_arches
    [ "$status" -eq 0 ]
    [ -n "$output" ]
    [[ "$output" == *"x86_64"* ]]
    [[ "$output" == *"aarch64"* ]]
}

@test "build.sh dispatches its variants through apply_variant" {
    run dispatched_variants
    [ "$status" -eq 0 ]
    [ -n "$output" ]
    [[ "$output" == *"dx"* ]]
    [[ "$output" == *"nvidia"* ]]
}

@test "every dispatched variant has both a script and a system-files override root" {
    for variant in $(dispatched_variants); do
        require_dir "${SCRIPT_OVERRIDES}/${variant}"
        require_dir "${FILE_OVERRIDES}/${variant}"
    done
}

@test "every supported arch has both a script and a system-files override root" {
    for arch in $(supported_arches); do
        require_dir "${SCRIPT_OVERRIDES}/${arch}"
        require_dir "${FILE_OVERRIDES}/${arch}"
    done
}

@test "every arch/variant pair exists in both trees under its own grammar" {
    for arch in $(supported_arches); do
        for variant in $(dispatched_variants); do
            require_dir "${SCRIPT_OVERRIDES}/${arch}/${variant}"
            require_dir "${FILE_OVERRIDES}/${arch}-${variant}"
        done
    done
}

@test "no orphaned variant directory under build_scripts/overrides/<arch>" {
    local variants=()
    while IFS= read -r variant; do variants+=("${variant}"); done < <(dispatched_variants)

    for arch in $(supported_arches); do
        for dir in $(subdirs_of "${SCRIPT_OVERRIDES}/${arch}"); do
            if ! contains "${dir}" "${variants[@]}"; then
                echo "build_scripts/overrides/${arch}/${dir} is never dispatched by build.sh" >&2
                return 1
            fi
        done
    done
}

@test "no orphaned top-level directory under build_scripts/overrides" {
    local variants=() arches=()
    while IFS= read -r variant; do variants+=("${variant}"); done < <(dispatched_variants)
    while IFS= read -r arch; do arches+=("${arch}"); done < <(supported_arches)

    for dir in $(subdirs_of "${SCRIPT_OVERRIDES}"); do
        contains "${dir}" "${variants[@]}" && continue
        contains "${dir}" "${arches[@]}" && continue
        # shellcheck disable=SC2086
        contains "${dir}" ${NON_VARIANT_SCRIPT_DIRS} && continue
        echo "build_scripts/overrides/${dir} is never dispatched by build.sh" >&2
        return 1
    done
}

@test "no orphaned top-level directory under system_files_overrides" {
    local variants=() arches=() expected=()
    while IFS= read -r variant; do variants+=("${variant}"); done < <(dispatched_variants)
    while IFS= read -r arch; do arches+=("${arch}"); done < <(supported_arches)

    expected+=("${variants[@]}" "${arches[@]}")
    for arch in "${arches[@]}"; do
        for variant in "${variants[@]}"; do
            expected+=("${arch}-${variant}")
        done
    done

    for dir in $(subdirs_of "${FILE_OVERRIDES}"); do
        if ! contains "${dir}" "${expected[@]}"; then
            echo "system_files_overrides/${dir} is never copied by build.sh" >&2
            return 1
        fi
    done
}

@test "the arch/variant path grammar is stated only inside apply_variant" {
    local hits
    hits="$(grep -cE 'copy_systemfiles_for "\$\(arch\)-|run_buildscripts_for "\$\(arch\)/' "${BUILD_SCRIPT}")"
    [ "${hits}" -eq 2 ]

    run grep -nE 'copy_systemfiles_for "\$\(arch\)-|run_buildscripts_for "\$\(arch\)/' "${BUILD_SCRIPT}"
    local first last apply_start apply_end
    first="$(echo "${output}" | head -1 | cut -d: -f1)"
    last="$(echo "${output}" | tail -1 | cut -d: -f1)"
    apply_start="$(grep -n '^apply_variant()' "${BUILD_SCRIPT}" | cut -d: -f1)"
    apply_end="$(awk -v s="${apply_start}" 'NR>s && /^}/ {print NR; exit}' "${BUILD_SCRIPT}")"

    [ -n "${apply_start}" ]
    [ -n "${apply_end}" ]
    [ "${first}" -gt "${apply_start}" ]
    [ "${last}" -lt "${apply_end}" ]
}
