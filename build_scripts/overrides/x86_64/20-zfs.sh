#!/bin/bash
set ${CI:+-x} -euo pipefail

# /*
# Get Kernel Version
# */
KERNEL_SUFFIX=""
KERNEL_NAME="kernel"
KERNEL_VRA="$(rpm -q "$KERNEL_NAME" --queryformat '%{EVR}.%{ARCH}')"
QUALIFIED_KERNEL="$(rpm -qa | grep -P 'kernel-(|'"$KERNEL_SUFFIX"'-)(\d+\.\d+\.\d+)' | sed -E 's/kernel-(|'"$KERNEL_SUFFIX"'-)//' | tail -n 1)"

# /*
### install base server ZFS packages and sanoid dependencies
# */
mapfile -t ZFS_RPMS < <(
    find /tmp/akmods-zfs-rpms/kmods/zfs -maxdepth 1 -type f -name '*.rpm' \
        ! -name 'python3-pyzfs-*.rpm' -print
)
if ((${#ZFS_RPMS[@]} == 0)); then
    echo 'ERROR: no ZFS RPMs were provided by the akmods image' >&2
    exit 1
fi
dnf -y install "${ZFS_RPMS[@]}"


  # python3-pyzfs requires python3.13dist(cffi) which is not available in CentOS Stream 10
  # Install it separately if the package exists and dependencies can be resolved
  dnf -y install --skip-broken /tmp/akmods-zfs-rpms/kmods/zfs/python3-pyzfs-*.rpm || true

# /*
# depmod ran automatically with zfs 2.1 but not with 2.2
# */
depmod -a "${KERNEL_VRA}"

# Autoload ZFS module
echo "zfs" >/usr/lib/modules-load.d/zfs.conf

/usr/bin/dracut --no-hostonly --kver "$QUALIFIED_KERNEL" --reproducible --zstd -v --add ostree -f "/lib/modules/$QUALIFIED_KERNEL/initramfs.img"
