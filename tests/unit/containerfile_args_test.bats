#!/usr/bin/env bats

# Guard for the Containerfile build-arg contract (bluefin-lts#559):
#   1. every ARG declaration has at least one consumer, and
#   2. no ARG is declared with two different default values.
# Dead declarations like the removed BASE_IMAGE_SHA and the post-FROM
# MAJOR_VERSION="lts" fail here instead of accumulating again.

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CONTAINERFILE="${REPO_ROOT}/Containerfile"

arg_names() {
    grep -oP '^ARG\s+\K[A-Za-z_][A-Za-z0-9_]*' "${CONTAINERFILE}" | sort -u
}

@test "containerfile: every ARG has a consumer" {
    local arg
    while IFS= read -r arg; do
        # Consumer = interpolated anywhere in the Containerfile outside the
        # ARG's own declaration line(s) (FROM, ENV, RUN substitution)...
        if grep -vE "^ARG[[:space:]]+${arg}(=|[[:space:]]|$)" "${CONTAINERFILE}" \
            | grep -qE "\\\$\{?${arg}\b"; then
            continue
        fi
        # ...or read by a build script / shipped file. Word-boundary match so
        # MAJOR_VERSION does not match MAJOR_VERSION_NUMBER.
        if grep -rwq "${arg}" \
            "${REPO_ROOT}/build_scripts" \
            "${REPO_ROOT}/system_files" \
            "${REPO_ROOT}/system_files_overrides" \
            "${REPO_ROOT}/scripts" 2>/dev/null; then
            continue
        fi
        echo "ARG ${arg} has no consumer: not interpolated in Containerfile and not read by any build script"
        return 1
    done < <(arg_names)
}

@test "containerfile: no ARG is declared with conflicting defaults" {
    # Extract "NAME default" pairs from declarations of the form
    #   ARG NAME="${NAME:-default}"
    # and fail if any NAME maps to more than one distinct default.
    local dupes
    dupes=$(grep -oP '^ARG\s+\K[A-Za-z_][A-Za-z0-9_]*="\$\{[A-Za-z_][A-Za-z0-9_]*:-[^}]+\}"' "${CONTAINERFILE}" \
        | sed -E 's/^([A-Za-z_][A-Za-z0-9_]*)="\$\{[A-Za-z_][A-Za-z0-9_]*:-([^}]*)\}"$/\1 \2/' \
        | sort -u \
        | awk '{print $1}' \
        | uniq -d)
    if [[ -n "${dupes}" ]]; then
        echo "ARG(s) declared with conflicting defaults: ${dupes}"
        return 1
    fi
}
