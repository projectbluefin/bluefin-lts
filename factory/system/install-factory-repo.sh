# Install the GNOME stack from the factory repository.
#
# The factory publishes a signed OCI image whose only content is a
# createrepo_c repository. It is copied in here and dnf is pointed at it over
# file://. That keeps the whole supply chain inside this organisation: no
# third-party package service sits between a source release and the shipped
# image.
#
# Sourced rather than written inline, because the repository file has to exist
# before the first dnf call that might use it, and the versionlock set below is
# read from the same manifest the package install uses.

set -euo pipefail

FACTORY_REPO_DIR=/run/factory-packages

# The factory repository outranks the base image for the names it provides.
# Without this, dnf may satisfy a name from AppStream/CRB and leave the
# factory's build unused -- the exact skew versionlocking exists to catch.
cat > /etc/yum.repos.d/bluefin-factory.repo <<EOF
[bluefin-factory]
name=Project Bluefin GNOME factory
baseurl=file://${FACTORY_REPO_DIR}
enabled=1
gpgcheck=0
priority=1
EOF

# Report what the factory actually contributed, so a build log shows which
# packages came from it. This is informational and must not fail the build.
echo "Factory repository contents:"
ls "${FACTORY_REPO_DIR}"/*.rpm 2>/dev/null | wc -l || echo 0