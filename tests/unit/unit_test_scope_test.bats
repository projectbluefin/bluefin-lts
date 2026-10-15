#!/usr/bin/env bats

# Drift gate: the BATS suite is the single source of truth for which source
# trees unit testing guards. .github/workflows/unit-tests.yml restates that set
# in its pull_request paths filter, and the two silently diverged: countme_test
# asserts on system_files/, which the filter did not list, so a PR editing the
# guarded unit never ran the test guarding it (#643).
#
# These tests extract every top-level tree referenced by tests/unit/*.bats
# (always via "${SCRIPT_DIR}/../../<tree>") and fail if the workflow trigger
# does not cover it.
#
# Run with: bats tests/unit/unit_test_scope_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORKFLOW="${REPO_ROOT}/.github/workflows/unit-tests.yml"

# Top-level repo entries the suite reads, one per line.
suite_subjects() {
    grep -hEo '\.\./\.\./[A-Za-z0-9_.-]+' "${SCRIPT_DIR}"/*.bats \
        | sed 's|\.\./\.\./||' \
        | sort -u
}

# Entries of on.pull_request.paths in unit-tests.yml, one per line, unquoted.
# Only the paths block under `pull_request:` counts; a `push.paths` block
# (or any other trigger's) is ignored.
workflow_paths() {
    awk '
        /^  [A-Za-z_]+:/ { in_pr = ($0 ~ /^  pull_request:/); in_paths = 0; next }
        /^[^[:space:]]/ { in_pr = 0; in_paths = 0; next }
        in_pr && /^[[:space:]]*paths:[[:space:]]*$/ { in_paths = 1; next }
        in_paths && /^[[:space:]]*#/ { next }
        in_paths && /^[[:space:]]*-[[:space:]]*/ {
            sub(/^[[:space:]]*-[[:space:]]*/, "")
            gsub(/["\x27]/, "")
            print
            next
        }
        in_paths { in_paths = 0 }
    ' "${WORKFLOW}"
}

@test "unit-test scope: the workflow declares a pull_request paths filter" {
    [ -f "${WORKFLOW}" ]
    run workflow_paths
    [ "$status" -eq 0 ]
    [ -n "$output" ]
}

@test "unit-test scope: the suite reads at least one source tree" {
    run suite_subjects
    [ "$status" -eq 0 ]
    [ -n "$output" ]
}

@test "unit-test scope: no new tree escapes the workflow paths filter" {
    local -a patterns=()
    while IFS= read -r pattern; do
        patterns+=("${pattern}")
    done < <(workflow_paths)

    local missing=""
    while IFS= read -r subject; do
        local covered=1
        for pattern in "${patterns[@]}"; do
            if [ "${pattern}" = "${subject}" ] || [ "${pattern}" = "${subject}/**" ]; then
                covered=0
                break
            fi
        done
        if [ "${covered}" -ne 0 ]; then
            missing="${missing} ${subject}"
        fi
    done < <(suite_subjects)

    if [ -n "${missing}" ]; then
        echo "tests/unit/*.bats read these trees, but unit-tests.yml"
        echo "on.pull_request.paths does not list them:${missing}"
        echo "Add '<tree>/**' (or the exact file) to the paths filter so a pull"
        echo "request touching them runs the tests that guard them."
        return 1
    fi
}

@test "unit-test scope: every tree the suite reads exists in the repository" {
    local missing=""
    while IFS= read -r subject; do
        if [ ! -e "${REPO_ROOT}/${subject}" ]; then
            missing="${missing} ${subject}"
        fi
    done < <(suite_subjects)

    if [ -n "${missing}" ]; then
        echo "tests/unit/*.bats reference repository entries that do not exist:${missing}"
        return 1
    fi
}
