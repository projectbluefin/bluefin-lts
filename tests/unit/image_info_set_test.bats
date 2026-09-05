#!/usr/bin/env bats

# Unit tests for build_scripts/scripts/image-info-set
#
# image-info-set rewrites /usr/share/ublue-os/image-info.json with the flavor
# the variant build actually produced. Downstream consumers (ujust recipes,
# fastfetch, update tooling, bug reports) read image-flavor/image-name/
# image-ref from that file, so a wrong or blanked value ships in the image and
# misroutes every one of them. 90-image-info.sh generates the file and is
# covered by image_info_test.bats; the per-variant rewrite performed by
# image-info-set had no coverage.
#
# Run with: bats tests/unit/image_info_set_test.bats

SCRIPT_DIR="$(cd "$(dirname "$BATS_TEST_FILENAME")" && pwd)"
IMAGE_INFO_SET="${SCRIPT_DIR}/../../build_scripts/scripts/image-info-set"

setup() {
    if ! command -v jq >/dev/null 2>&1; then
        skip "jq is required by image-info-set"
    fi

    IMAGE_INFO_FILE="${BATS_TEST_TMPDIR}/image-info.json"
    cat > "${IMAGE_INFO_FILE}" <<'EOF'
{
  "image-name": "bluefin-lts",
  "image-flavor": "main",
  "image-vendor": "projectbluefin",
  "image-ref": "ostree-image-signed:docker://ghcr.io/projectbluefin/bluefin-lts",
  "image-tag": "stable",
  "centos-version": "10"
}
EOF
}

run_image_info_set() {
    IMAGE_INFO="${IMAGE_INFO_FILE}" run bash "${IMAGE_INFO_SET}" "$@"
}

json_field() {
    jq -r "$1" "${IMAGE_INFO_FILE}"
}

@test "image-info-set: script exists and is executable" {
    [ -x "${IMAGE_INFO_SET}" ]
}

@test "image-info-set: sets image-flavor from the positional argument" {
    run_image_info_set nvidia
    [ "$status" -eq 0 ]
    [ "$(json_field '."image-flavor"')" = "nvidia" ]
}

@test "image-info-set: FLAVOR environment variable wins over the argument" {
    IMAGE_INFO="${IMAGE_INFO_FILE}" FLAVOR=dx run bash "${IMAGE_INFO_SET}" nvidia
    [ "$status" -eq 0 ]
    [ "$(json_field '."image-flavor"')" = "dx" ]
}

@test "image-info-set: FLAVOR environment variable works with no argument" {
    IMAGE_INFO="${IMAGE_INFO_FILE}" FLAVOR=nvidia-open run bash "${IMAGE_INFO_SET}"
    [ "$status" -eq 0 ]
    [ "$(json_field '."image-flavor"')" = "nvidia-open" ]
}

@test "image-info-set: preserves image-name when IMAGE_NAME is not overridden" {
    run_image_info_set dx
    [ "$status" -eq 0 ]
    [ "$(json_field '."image-name"')" = "bluefin-lts" ]
}

@test "image-info-set: preserves image-ref when IMAGE_REF is not overridden" {
    run_image_info_set dx
    [ "$status" -eq 0 ]
    [ "$(json_field '."image-ref"')" = "ostree-image-signed:docker://ghcr.io/projectbluefin/bluefin-lts" ]
}

@test "image-info-set: IMAGE_NAME overrides the recorded image name" {
    IMAGE_INFO="${IMAGE_INFO_FILE}" IMAGE_NAME=bluefin-lts-dx run bash "${IMAGE_INFO_SET}" dx
    [ "$status" -eq 0 ]
    [ "$(json_field '."image-name"')" = "bluefin-lts-dx" ]
}

@test "image-info-set: IMAGE_REF overrides the recorded image ref" {
    IMAGE_INFO="${IMAGE_INFO_FILE}" \
        IMAGE_REF="ostree-image-signed:docker://ghcr.io/projectbluefin/bluefin-lts-dx" \
        run bash "${IMAGE_INFO_SET}" dx
    [ "$status" -eq 0 ]
    [ "$(json_field '."image-ref"')" = "ostree-image-signed:docker://ghcr.io/projectbluefin/bluefin-lts-dx" ]
}

@test "image-info-set: leaves unrelated keys untouched" {
    run_image_info_set dx
    [ "$status" -eq 0 ]
    [ "$(json_field '."image-vendor"')" = "projectbluefin" ]
    [ "$(json_field '."image-tag"')" = "stable" ]
    [ "$(json_field '."centos-version"')" = "10" ]
}

@test "image-info-set: adds no keys and drops none" {
    run_image_info_set dx
    [ "$status" -eq 0 ]
    [ "$(jq -r 'keys | join(",")' "${IMAGE_INFO_FILE}")" = "centos-version,image-flavor,image-name,image-ref,image-tag,image-vendor" ]
}

@test "image-info-set: result is valid JSON" {
    run_image_info_set dx
    [ "$status" -eq 0 ]
    jq -e . "${IMAGE_INFO_FILE}" >/dev/null
}

@test "image-info-set: is idempotent when run twice with the same flavor" {
    run_image_info_set dx
    [ "$status" -eq 0 ]
    first="$(jq -S -c . "${IMAGE_INFO_FILE}")"

    run_image_info_set dx
    [ "$status" -eq 0 ]
    [ "$(jq -S -c . "${IMAGE_INFO_FILE}")" = "${first}" ]
}

@test "image-info-set: a later run overwrites the previous flavor" {
    run_image_info_set dx
    [ "$status" -eq 0 ]
    run_image_info_set nvidia
    [ "$status" -eq 0 ]
    [ "$(json_field '."image-flavor"')" = "nvidia" ]
}

@test "image-info-set: leaves the file world readable (0644)" {
    chmod 0600 "${IMAGE_INFO_FILE}"
    run_image_info_set dx
    [ "$status" -eq 0 ]
    [ "$(stat -c '%a' "${IMAGE_INFO_FILE}")" = "644" ]
}

@test "image-info-set: file is never left empty" {
    run_image_info_set dx
    [ "$status" -eq 0 ]
    [ -s "${IMAGE_INFO_FILE}" ]
}

@test "image-info-set: fails when the image-info file is missing" {
    rm -f "${IMAGE_INFO_FILE}"
    run_image_info_set dx
    [ "$status" -ne 0 ]
}

@test "image-info-set: fails on malformed image-info JSON" {
    printf 'not json' > "${IMAGE_INFO_FILE}"
    run_image_info_set dx
    [ "$status" -ne 0 ]
}

@test "image-info-set: flavors with a hyphen survive the rewrite" {
    run_image_info_set nvidia-open
    [ "$status" -eq 0 ]
    [ "$(json_field '."image-flavor"')" = "nvidia-open" ]
}

# Documents current behaviour, not desired behaviour: with neither FLAVOR nor a
# positional argument the script blanks image-flavor instead of refusing to run.
@test "image-info-set: with no flavor supplied image-flavor is blanked" {
    run_image_info_set
    [ "$status" -eq 0 ]
    [ "$(json_field '."image-flavor"')" = "" ]
}
