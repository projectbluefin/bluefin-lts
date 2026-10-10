ARG MAJOR_VERSION="${MAJOR_VERSION:-c10s}"
# Trigger a fresh testing rebuild after the post-testing workflow dispatch condition fix.
ARG BASE_IMAGE_SHA="${BASE_IMAGE_SHA:-sha256-feea845d2e245b5e125181764cfbc26b6dacfb3124f9c8d6a2aaa4a3f91082ed}"
ARG AKMODS_VERSION="${AKMODS_VERSION:-coreos-stable-43}"
ARG COMMON_IMAGE_REF
ARG BREW_IMAGE_REF
# The GNOME stack this image installs, built by factory/ against this same
# CentOS Stream base. Pinned by digest: a tag would let the repository change
# under a rebuild, which would make the image unreproducible and the packages
# in it unattributable. A local empty stage is the default until a factory
# digest is available, preserving the existing GNOME installation path.
ARG GNOME_PACKAGES_IMAGE_REF="gnome_packages_empty"
# Upstream mounts akmods-zfs and akmods-nvidia-open; LTS defaults to CoreOS-stable kernel tags.
# Keep this build recipe in sync with the testing promotion pipeline.
FROM ghcr.io/ublue-os/akmods-zfs:${AKMODS_VERSION} AS akmods_zfs
FROM ghcr.io/ublue-os/akmods-nvidia-open:${AKMODS_VERSION} AS akmods_nvidia_open
FROM ${COMMON_IMAGE_REF} AS common
FROM ${BREW_IMAGE_REF} AS brew
FROM scratch AS gnome_packages_empty
COPY factory/empty/ /factory/
# The factory publishes a createrepo_c repository as the image's only
# content. COPY --from of a scratch image carries that directory and nothing
# else, so there is no shell or package manager to reason about in the source
# stage.
FROM ${GNOME_PACKAGES_IMAGE_REF} AS gnome_packages
FROM scratch AS ctx
COPY system_files /files
COPY --from=brew /system_files /files
COPY --from=common /system_files/shared /files
COPY --from=common /system_files/bluefin /files
COPY system_files_overrides /overrides
COPY build_scripts /build_scripts
COPY image-versions.yaml /image-versions.yaml
COPY factory /factory

ARG MAJOR_VERSION="${MAJOR_VERSION:-c10s}"
FROM quay.io/centos-bootc/centos-bootc:$MAJOR_VERSION

ARG ENABLE_DX="${ENABLE_DX:-0}"
ARG ENABLE_NVIDIA="${ENABLE_NVIDIA:-0}"
ARG FEDORA_AKMODS_VERSION="${FEDORA_AKMODS_VERSION:-43}"
ARG GNOME_VERSION="${GNOME_VERSION:-50}"
ARG IMAGE_NAME="${IMAGE_NAME:-bluefin}"
ARG IMAGE_VENDOR="${IMAGE_VENDOR:-ublue-os}"
ARG MAJOR_VERSION="${MAJOR_VERSION:-lts}"
ARG SHA_HEAD_SHORT="${SHA_HEAD_SHORT:-deadbeef}"
ARG GNOME_PACKAGES_IMAGE_REF
ENV FEDORA_AKMODS_VERSION="${FEDORA_AKMODS_VERSION}"

# The factory's RPM repository, installed by the GNOME group below. Copied in
# rather than mounted: the RPMs must survive the RUN for the installed
# packages to record a valid file reference for rpm verification, and a
# tmpfs mount would leave dangling references in the rpm database.
COPY --from=gnome_packages /factory /run/gnome-packages

RUN --mount=type=tmpfs,dst=/opt \
  --mount=type=tmpfs,dst=/tmp \
  --mount=type=tmpfs,dst=/var \
  --mount=type=tmpfs,dst=/boot \
  --mount=type=bind,from=akmods_zfs,src=/rpms,dst=/tmp/akmods-zfs-rpms \
  --mount=type=bind,from=akmods_zfs,src=/kernel-rpms,dst=/tmp/kernel-rpms \
  --mount=type=bind,from=akmods_nvidia_open,src=/rpms,dst=/tmp/akmods-nvidia-open-rpms \
  --mount=type=bind,from=ctx,source=/,target=/run/context \
  /run/context/build_scripts/build.sh

# Makes `/opt` writeable by default
# Needs to be here to make the main image build strict (no /opt there)
RUN rm -rf /opt && ln -s /var/opt /opt
