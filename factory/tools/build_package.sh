#!/usr/bin/env bash
# CentOS Stream container lane. Prior-wave RPMs and the seed are assembled
# outside the container; dependencies and the build share this one root.
set -euo pipefail
: "${PACKAGE:?}"
spec="/repo/factory/packages/$PACKAGE/$PACKAGE.spec"
test -f "$spec"
dnf -y install rpm-build dnf-plugins-core createrepo_c redhat-rpm-config
# CRB is required, so an enablement failure must not be ignored.
dnf config-manager --set-enabled crb
if find /prior -name '*.rpm' -print -quit | read -r _; then
    createrepo_c /prior
    printf '[factory]\nname=factory\nbaseurl=file:///prior\nenabled=1\ngpgcheck=0\npriority=1\n' > /etc/yum.repos.d/factory.repo
fi
python3 /repo/factory/tools/source_pipeline.py verify-staged --package "$PACKAGE"
args=(--define "_topdir /repo/work/rpmbuild/$PACKAGE"
      --define "_sourcedir /repo/factory/packages/$PACKAGE"
      --define "_specdir /repo/factory/packages/$PACKAGE"
      --define "dist .el10")
dnf -y builddep -D 'dist .el10' -D "_sourcedir /repo/factory/packages/$PACKAGE" "$spec"
# Adapted from utah-packages: exit 11 requests installation of generated
# BuildRequires. Other failures must retain their original exit status.
ready=false
for attempt in 1 2 3 4 5; do
    rm -f /repo/work/rpmbuild/"$PACKAGE"/SRPMS/*.buildreqs.nosrc.rpm
    status=0
    rpmbuild -br "$spec" "${args[@]}" || status=$?
    if [ "$status" -eq 0 ]; then ready=true; break; fi
    [ "$status" -eq 11 ] || exit "$status"
    generated=(/repo/work/rpmbuild/"$PACKAGE"/SRPMS/*.buildreqs.nosrc.rpm)
    test -f "${generated[0]}"
    dnf -y builddep "${generated[0]}"
done
if [ "$ready" != true ]; then
    echo 'generated BuildRequires did not converge after five attempts' >&2
    exit 1
fi
rpmbuild -ba "$spec" "${args[@]}"
mkdir -p "/repo/work/rpms/$PACKAGE"
find "/repo/work/rpmbuild/$PACKAGE/RPMS" -name '*.rpm' \
    -exec cp -v {} "/repo/work/rpms/$PACKAGE/" \;
