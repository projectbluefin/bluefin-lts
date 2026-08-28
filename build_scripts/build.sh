#!/usr/bin/env bash

# This file needs to exist otherwise running this in a RUN label makes it so bash strict mode doesnt work.
# Thus leading to silent failures

set -eo pipefail

# Do not rely on any of these scripts existing in a specific path
# Make the names as descriptive as possible and everything that uses dnf for package installation/removal should have `packages-` as a prefix.

CONTEXT_PATH="$(realpath "$(dirname "$0")/..")" # should return /run/context
BUILD_SCRIPTS_PATH="$(realpath "$(dirname "$0")")"
MAJOR_VERSION_NUMBER="$(sh -c '. /usr/lib/os-release ; echo ${VERSION_ID%.*}')"
SCRIPTS_PATH="$(realpath "$(dirname "$0")/scripts")"
export SCRIPTS_PATH
export PATH="${SCRIPTS_PATH}:${PATH}"
export MAJOR_VERSION_NUMBER

run_buildscripts_for() {
	WHAT=$1
	shift
	# Complex "find" expression here since there might not be any overrides
	find "${BUILD_SCRIPTS_PATH}/overrides/$WHAT" -maxdepth 1 -iname "*-*.sh" -type f -print0 | sort --zero-terminated --sort=human-numeric | while IFS= read -r -d $'\0' script ; do
		if [ "${CUSTOM_NAME}" != "" ] ; then
			WHAT=$CUSTOM_NAME
		fi
		printf "::group:: ===$WHAT-%s===\n" "$(basename "$script")"
		"$(realpath "$script")"
		printf "::endgroup::\n"
	done
}

copy_systemfiles_for() {
	WHAT=$1
	shift
	DISPLAY_NAME=$WHAT
	if [ "${CUSTOM_NAME}" != "" ] ; then
		DISPLAY_NAME=$CUSTOM_NAME
	fi
	printf "::group:: ===%s-file-copying===\n" "${DISPLAY_NAME}"
	cp -avf "${CONTEXT_PATH}/overrides/$WHAT/." /
	printf "::endgroup::\n"
}

# Single source of truth for the variant override path grammar.
# The two override trees are keyed on the same (arch, variant) axis but use
# different path grammars: system_files_overrides is flat and hyphen-separated
# (<arch>-<variant>) while build_scripts/overrides is nested and slash-separated
# (<arch>/<variant>). Keep that mapping here so call sites never restate it.
apply_variant() {
	VARIANT_NAME=$1
	shift
	copy_systemfiles_for "$VARIANT_NAME"
	run_buildscripts_for "$VARIANT_NAME"
	copy_systemfiles_for "$(arch)-$VARIANT_NAME"
	run_buildscripts_for "$(arch)/$VARIANT_NAME"
}

# Satisfy dracut-install when installing the /root symlink pointing to var/roothome
mkdir -p /var/roothome

run_buildscripts_for base

CUSTOM_NAME="bluefin"
copy_systemfiles_for ../files
run_buildscripts_for ..
CUSTOM_NAME=""

copy_systemfiles_for "$(arch)"
run_buildscripts_for "$(arch)"

if [ "$ENABLE_DX" == "1" ]; then
	apply_variant dx
fi

if [ "$ENABLE_NVIDIA" == "1" ]; then
	apply_variant nvidia
fi

printf "::group:: ===Image Cleanup===\n"
# Ensure these get run at the _end_ of the build no matter what
"${BUILD_SCRIPTS_PATH}/cleanup.sh"
printf "::endgroup::\n"
