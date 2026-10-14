#!/usr/bin/env bash

set -xeuo pipefail

IMAGE_REF="ostree-image-signed:docker://ghcr.io/${IMAGE_VENDOR}/${IMAGE_NAME}"
IMAGE_INFO="/usr/share/ublue-os/image-info.json"
IMAGE_FLAVOR="main"
IMAGE_TAG="stable/testing"

tee "$IMAGE_INFO" <<EOF
{
  "image-name": "${IMAGE_NAME}",
  "image-ref": "${IMAGE_REF}",
  "image-flavor": "${IMAGE_FLAVOR}",
  "image-vendor": "${IMAGE_VENDOR}",
  "image-tag": "${IMAGE_TAG}",
  "centos-version": "${MAJOR_VERSION_NUMBER}"
}
EOF
chmod 0644 "${IMAGE_INFO}"

IMAGE_PRETTY_NAME="Uranium"
# TODO(rebrand): thalliumsuite.io / docs.thalliumsuite.io do not resolve yet.
# Home points at this repository; documentation still points at the existing
# projectbluefin LTS docs site until the new docs are published.
HOME_URL="https://github.com/thallium-suite/uranium"
DOCUMENTATION_URL="https://docs.projectbluefin.io"
SUPPORT_URL="https://github.com/thallium-suite/uranium/issues/"
BUG_SUPPORT_URL="https://github.com/thallium-suite/uranium/issues/"
CODE_NAME="Achillobator"

# OS Release File (changed in order with upstream)
sed -i -f - /usr/lib/os-release <<EOF
s/^NAME=.*/NAME=\"${IMAGE_PRETTY_NAME}\"/
s|^VERSION_CODENAME=.*|VERSION_CODENAME=\"${CODE_NAME}\"|
s/^VARIANT_ID=.*/VARIANT_ID=${IMAGE_NAME}/
s/^PRETTY_NAME=.*/PRETTY_NAME=\"${IMAGE_PRETTY_NAME}\"/
s|^HOME_URL=.*|HOME_URL=\"${HOME_URL}\"|
s|^BUG_REPORT_URL=.*|BUG_REPORT_URL=\"${BUG_SUPPORT_URL}\"|
s|^CPE_NAME=\"cpe:/o:centos:centos|CPE_NAME=\"cpe:/o:universal-blue:uranium|

/^REDHAT_BUGZILLA_PRODUCT=/d
/^REDHAT_BUGZILLA_PRODUCT_VERSION=/d
/^REDHAT_SUPPORT_PRODUCT=/d
/^REDHAT_SUPPORT_PRODUCT_VERSION=/d
EOF

tee -a /usr/lib/os-release <<EOF
DOCUMENTATION_URL="${DOCUMENTATION_URL}"
SUPPORT_URL="${SUPPORT_URL}"
DEFAULT_HOSTNAME="uranium"
BUILD_ID="${SHA_HEAD_SHORT:-deadbeef}"
EOF

# Weekly user count for fastfetch.
# Removed with the Bluefin branding: the only endpoint available was
# ublue-os/countme's bluefin.json, which reports Bluefin's install count.
# fastfetch.jsonc still runs `cat` on this path, so write a neutral
# placeholder rather than letting it fail on every invocation.
# Restore the real fetch once a Uranium endpoint is published upstream.
printf 'N/A\n' > /usr/share/ublue-os/fastfetch-user-count

# bazaar weekly downloads used for fastfetch
curl -X 'GET' \
'https://flathub.org/api/v2/stats/io.github.kolunmi.Bazaar?all=false&days=1' \
-H 'accept: application/json' | jq -r ".installs_last_7_days" | numfmt --to=si --round=nearest > /usr/share/ublue-os/bazaar-install-count
