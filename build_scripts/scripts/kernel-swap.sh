#!/bin/bash
# /*
#shellcheck disable=SC1083
# */

set ${CI:+-x} -euo pipefail

# /*
### Kernel Swap - Install kernel from mounted akmods containers
### Containerfile provides the correct kernel via AKMODS_VERSION:
###   - centos-10 for standard builds
###   - coreos-stable-<version> for HWE/nvidia builds (follows Fedora CoreOS stable)
# */

KERNEL_NAME="kernel"

# Remove existing kernel packages
# Always remove these packages as kernel cache provides signed versions
PKGS=( "${KERNEL_NAME}" "${KERNEL_NAME}-core" "${KERNEL_NAME}-modules" "${KERNEL_NAME}-modules-core" "${KERNEL_NAME}-modules-extra" "${KERNEL_NAME}-uki-virt" )
for pkg in "${PKGS[@]}"; do
  rpm --erase "$pkg" --nodeps || true
done

# Install kernel from mounted /tmp/kernel-rpms (provided by Containerfile akmods mounts)
echo "Installing kernel from mounted kernel-rpms..."
find /tmp/kernel-rpms

# Extract version from the first kernel rpm filename (handles both .el10 and .fc42 dist tags)
# shellcheck disable=SC2012
CACHED_VERSION=$(cd /tmp/kernel-rpms && ls kernel-[0-9]*.rpm 2>/dev/null | head -1 | sed -E 's/^kernel-//;s/\.rpm$//')

if [[ -z "$CACHED_VERSION" ]]; then
  echo "ERROR: Could not detect kernel version from /tmp/kernel-rpms"
  ls -la /tmp/kernel-rpms/
  exit 1
fi

echo "Detected kernel version: ${CACHED_VERSION}"

INSTALL_PKGS=( "${KERNEL_NAME}" "${KERNEL_NAME}-core" "${KERNEL_NAME}-modules" "${KERNEL_NAME}-modules-core" "${KERNEL_NAME}-modules-extra" "${KERNEL_NAME}-uki-virt" "${KERNEL_NAME}-devel" "${KERNEL_NAME}-devel-matched" )

RPM_NAMES=()
for pkg in "${INSTALL_PKGS[@]}"; do
  RPM_NAMES+=("/tmp/kernel-rpms/$pkg-$CACHED_VERSION.rpm")
done

# /boot and /var/tmp are separate tmpfs mounts inside the container build RUN layer;
# rename(2) across two different devices fails with EXDEV (os error 18).
#
# The dracut.conf.d tmpdir approach (PR #248) sets tmpdir=/boot but does NOT fix the
# EXDEV when the kernel-install hook uses its own internal rename: rpm-ostree's
# 05-rpmostree.install calls dracut via kernel-install which internally renames a
# temp file from the tmpfs to the overlay filesystem, triggering EXDEV regardless
# of the tmpdir setting.
#
# Fix: install kernel RPMs with tsflags=noscripts to skip the %posttrans
# kernel-install scriptlet entirely, then generate the initramfs with an explicit
# dracut call. The explicit -f write goes directly to the destination (no
# cross-device rename), so tmpdir=/boot and output on the overlay work fine.
#
# centos-bootc:c10s >= 6.12.0-233 no longer pre-installs kernel-uki-virt, so
# kernel-swap reinstalls kernel-core from scratch, re-triggering the POSTTRANS
# scriptlet and the EXDEV regression. This noscripts approach is immune to that.
mkdir -p /etc/dracut.conf.d
echo 'tmpdir="/boot"' > /etc/dracut.conf.d/01-tmpdir.conf

dnf -y install --setopt=tsflags=noscripts "${RPM_NAMES[@]}"

# Generate initramfs explicitly — mirrors the approach used in 20-nvidia.sh.
# Direct -f output avoids the cross-device rename that kernel-install uses internally.
dracut --no-hostonly --kver "${CACHED_VERSION}" --reproducible --tmpdir /boot --zstd -v --add ostree -f "/lib/modules/${CACHED_VERSION}/initramfs.img"

# HWE-specific: Install common akmods
# These are not in the base mounts, so we download them via skopeo
if [[ "${ENABLE_HWE:-0}" -eq 1 || "${ENABLE_NVIDIA:-0}" -eq 1 ]]; then
  echo "HWE mode enabled - installing common akmods..."

  # Detect kernel version from installed kernel
  KERNEL_VERSION=$(rpm -q kernel --queryformat '%{VERSION}-%{RELEASE}.%{ARCH}')
  echo "Detected kernel version: ${KERNEL_VERSION}"

  AKMODS_FLAVOR="coreos-stable"
  # Derive Fedora version from the installed kernel (e.g., 7.0.8-200.fc44.x86_64 → 44)
  FEDORA_VERSION=$(echo "${KERNEL_VERSION}" | grep -oP 'fc\K[0-9]+')
  if [[ -z "${FEDORA_VERSION}" ]]; then
    # Fall back to the build-arg passed at image build time
    FEDORA_VERSION="${FEDORA_AKMODS_VERSION:-43}"
  fi

  # Create writable directory for common akmods downloads (tmpfs /tmp is mounted)
  COMMON_AKMODS_DIR="/run/common-akmods"
  mkdir -p "$COMMON_AKMODS_DIR"

  # Fetch common akmods container for the kernel version
  echo "Downloading common akmods for kernel ${KERNEL_VERSION}..."
  skopeo copy --retry-times 3 \
    docker://ghcr.io/ublue-os/akmods:"${AKMODS_FLAVOR}"-"${FEDORA_VERSION}"-"${KERNEL_VERSION}" \
    dir:"$COMMON_AKMODS_DIR"/akmods-container

  # Extract the common akmods rpms
  AKMODS_TARGZ=$(jq -r '.layers[].digest' <"$COMMON_AKMODS_DIR"/akmods-container/manifest.json | cut -d : -f 2)
  tar -xzf "$COMMON_AKMODS_DIR"/akmods-container/"$AKMODS_TARGZ" -C "$COMMON_AKMODS_DIR"

  # Install common akmods if they exist
  if [[ -d "$COMMON_AKMODS_DIR"/rpms ]]; then
    echo "Available common akmods packages:"
    ls -lh "$COMMON_AKMODS_DIR"/rpms/ || true
    ls -lh "$COMMON_AKMODS_DIR"/rpms/kmods/ || true

    echo "Installing common akmods with dependencies..."
    # Install both the -kmod-common packages (from rpms/) and kmod-* packages (from rpms/kmods/)
    dnf -y install \
      "$COMMON_AKMODS_DIR"/rpms/*xone*.rpm \
      "$COMMON_AKMODS_DIR"/rpms/*openrazer*.rpm \
      "$COMMON_AKMODS_DIR"/rpms/*framework-laptop*.rpm \
      "$COMMON_AKMODS_DIR"/rpms/*v4l2loopback*.rpm \
      "$COMMON_AKMODS_DIR"/rpms/kmods/*xone*.rpm \
      "$COMMON_AKMODS_DIR"/rpms/kmods/*openrazer*.rpm \
      "$COMMON_AKMODS_DIR"/rpms/kmods/*framework-laptop*.rpm \
      "$COMMON_AKMODS_DIR"/rpms/kmods/*v4l2loopback*.rpm \
      || echo "Warning: Some common akmods failed to install (non-critical)"
  else
    echo "Warning: No rpms directory found in common akmods container"
  fi
  echo "Installed common akmods packages:"
  rpm -qa | grep -E 'xone|openrazer|framework|v4l2loopback' || true
  # Cleanup
  rm -rf "$COMMON_AKMODS_DIR"
else
  echo "Standard mode - common akmods not installed"
fi

# Remove build-time dracut tmpdir config — must not ship in the final image
rm -f /etc/dracut.conf.d/01-tmpdir.conf

# /*
### Version Lock kernel packages
# */
dnf versionlock add \
  "$KERNEL_NAME" \
  "$KERNEL_NAME"-core \
  "$KERNEL_NAME"-modules \
  "$KERNEL_NAME"-modules-core \
  "$KERNEL_NAME"-modules-extra

# Add akmods secureboot key
mkdir -p /etc/pki/akmods/certs
ghcurl "https://github.com/ublue-os/akmods/raw/main/certs/public_key.der" --retry 15 -Lo /etc/pki/akmods/certs/akmods-ublue.der
