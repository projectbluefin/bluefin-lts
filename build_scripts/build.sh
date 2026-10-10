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

# Satisfy dracut-install when installing the /root symlink pointing to var/roothome
mkdir -p /var/roothome

# The GNOME package factory. Its repository is copied into the image by the
# Containerfile; this enables it before any dnf call, so the base packages and
# the GNOME group below all resolve against the same repository.
#
# Runs before the base overrides because those install glib2, fontconfig and
# selinux-policy, and dnf decides which repository answers for a name at
# resolution time. Enabling it afterwards would mean those three come from the
# base image while GNOME comes from the factory -- the exact skew the
# versionlock set in 10-packages-image-base.sh exists to prevent.
if [ -d /run/gnome-packages ]; then
	printf "::group:: ===gnome-factory-repo===\n"
	"${CONTEXT_PATH}/factory/system/install-factory-repo.sh"
	printf "::endgroup::\n"
fi

run_buildscripts_for base

CUSTOM_NAME="bluefin"
copy_systemfiles_for ../files
run_buildscripts_for ..
CUSTOM_NAME=""

copy_systemfiles_for "$(arch)"
run_buildscripts_for "$(arch)"

if [ "$ENABLE_DX" == "1" ]; then
	copy_systemfiles_for dx
	run_buildscripts_for dx
	copy_systemfiles_for "$(arch)-dx"
	run_buildscripts_for "$(arch)/dx"
fi

if [ "$ENABLE_NVIDIA" == "1" ]; then
	copy_systemfiles_for nvidia
	run_buildscripts_for nvidia
	copy_systemfiles_for "$(arch)-nvidia"
	run_buildscripts_for "$(arch)/nvidia"
fi

printf "::group:: ===Image Cleanup===\n"
# Ensure these get run at the _end_ of the build no matter what
"${BUILD_SCRIPTS_PATH}/cleanup.sh"
printf "::endgroup::\n"
