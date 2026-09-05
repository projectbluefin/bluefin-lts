#!/usr/bin/env bash

set -xeuo pipefail

# Image cleanup
# Specifically called by build.sh

# The compose repos we used during the build are point in time repos that are
# not updated, so we don't want to leave them enabled.
dnf config-manager --set-disabled baseos-compose,appstream-compose

dnf clean all

# Rebuild the rpm database before committing. Package transactions executed
# under buildah's overlayfs leave the sqlite rpmdb (Basenames / Providename
# index B-trees) corrupted — `rpmdb --verifydb` reports "database disk image is
# malformed" even though plain `rpm -q` still answers. The damage only surfaces
# later for any image built on top of this one that runs dnf again (e.g. silent
# failed erasures, "transaction check vs depsolve" errors). Ship a clean db.
#
# `rpm --rebuilddb` cannot run in place here: it rebuilds into a sibling
# directory of %_dbpath and renames that over the original, and renaming a
# directory that comes from a lower overlayfs layer fails inside buildah
# ("failed to replace old database with new database"). Rebuild inside a
# writable copy (tmpfs, never lands in a layer) and move only the finished file
# back with --remove-destination so the shipped hardlink is rewritten in place.
if rpmdb --verifydb >/dev/null 2>&1; then
    echo "rpmdb integrity OK, no rebuild needed"
else
    echo "rpmdb is corrupt, rebuilding it"
    _rpmdb_path="$(rpm --eval '%_dbpath')"
    _rpmdb_repair_dir=/tmp/rpmdb-repair
    rm -rf "${_rpmdb_repair_dir}"
    mkdir -p "${_rpmdb_repair_dir}"
    cp "${_rpmdb_path}/rpmdb.sqlite" "${_rpmdb_repair_dir}/"
    rpm --dbpath "${_rpmdb_repair_dir}" --rebuilddb
    rpmdb --dbpath "${_rpmdb_repair_dir}" --verifydb
    rm -f "${_rpmdb_path}/rpmdb.sqlite-shm" "${_rpmdb_path}/rpmdb.sqlite-wal"
    cp --remove-destination "${_rpmdb_repair_dir}/rpmdb.sqlite" \
        "${_rpmdb_path}/rpmdb.sqlite"
    chmod 0644 "${_rpmdb_path}/rpmdb.sqlite"
    rm -rf "${_rpmdb_repair_dir}"
    # Fail the build loudly if the db is still not clean.
    rpmdb --verifydb
fi

rm -rf /.gitkeep /etc/dracut.conf.d/02-omit-unsupported-microcode.conf
find /var -mindepth 1 -delete
find /boot -mindepth 1 -delete
mkdir -p /var /boot

# Make /usr/local writeable
ln -s /var/usrlocal /usr/local

chmod 644 /usr/share/ublue-os/image-info.json

# FIXME: use --fix option once https://github.com/containers/bootc/pull/1152 is merged
bootc container lint --fatal-warnings || true
