#!/usr/bin/env bats
# Tests for the factory repository wiring in the image build.
#
# This is the seam between the package factory and the image: the Containerfile
# copies the factory's repository in, and build.sh enables it before any dnf
# call. Getting the ordering wrong is invisible until an image builds with
# half its GNOME from the base and half from the factory, which is exactly the
# skew the versionlock set exists to catch. So the ordering is asserted here.

setup() {
  REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
  BUILD_SH="${REPO_ROOT}/build_scripts/build.sh"
  INSTALL_REPO="${REPO_ROOT}/factory/system/install-factory-repo.sh"
}

@test "build.sh enables the factory repository before the base overrides run" {
  run grep -n 'install-factory-repo.sh' "${BUILD_SH}"
  [ "$status" -eq 0 ]

  # The line that runs the base overrides -- everything that installs
  # glib2, fontconfig and selinux-policy -- must come after it.
  local repo_line base_line
  repo_line=$(grep -n 'install-factory-repo.sh' "${BUILD_SH}" | head -1 | cut -d: -f1)
  base_line=$(grep -n '^run_buildscripts_for base$' "${BUILD_SH}" | head -1 | cut -d: -f1)

  [ -n "$repo_line" ]
  [ -n "$base_line" ]
  [ "$repo_line" -lt "$base_line" ]
}

@test "the factory repository is only enabled when it was actually copied in" {
  # The Containerfile stages the repository from the factory image. That
  # image has no digest until the factory publishes, so the copy is optional
  # and the build must still work without it -- using the base image's GNOME.
  run grep -n 'if \[ -d /run/gnome-packages \]' "${BUILD_SH}"
  [ "$status" -eq 0 ]
}

@test "install-factory-repo.sh writes a repo file dnf accepts" {
  run grep -q 'baseurl=file://' "${INSTALL_REPO}"
  [ "$status" -eq 0 ]

  # gpgcheck must be off: the repository is a file:// directory, not a
  # signed remote repo, and leaving it on makes every install fail on key
  # retrieval rather than on anything real.
  run grep -q 'gpgcheck=0' "${INSTALL_REPO}"
  [ "$status" -eq 0 ]

  # priority must put the factory ahead of the base image for the names it
  # provides, or dnf may satisfy a name from AppStream and leave the
  # factory's build unused.
  run grep -q 'priority=1' "${INSTALL_REPO}"
  [ "$status" -eq 0 ]
}

@test "the Containerfile stages the factory repository, not the RPMs directly" {
  local containerfile="${REPO_ROOT}/Containerfile"
  run grep -q 'COPY --from=gnome_packages /factory /run/gnome-packages' "${containerfile}"
  [ "$status" -eq 0 ]
}

@test "the Containerfile declares the factory image ref as an optional build arg" {
  local containerfile="${REPO_ROOT}/Containerfile"
  # Defaulted to empty so a build with no factory image published still
  # works. A required arg would break every build until the first publish.
  run grep -q 'ARG GNOME_PACKAGES_IMAGE_REF=""' "${containerfile}"
  [ "$status" -eq 0 ]
}

@test "the build recipe omits the factory arg entirely when no digest is pinned" {
  # "FROM ''" is a parse error, not a fallback, so an empty digest must
  # result in the argument not being passed at all.
  run grep -q 'GNOME_PACKAGES_IMAGE_REF=' "${REPO_ROOT}/Justfile"
  [ "$status" -eq 0 ]

  run grep -q 'select(.name == "gnome_packages")' "${REPO_ROOT}/Justfile"
  [ "$status" -eq 0 ]
}

@test "image-versions.yaml has an entry for the factory image" {
  run grep -q 'name: gnome_packages' "${REPO_ROOT}/image-versions.yaml"
  [ "$status" -eq 0 ]
}
