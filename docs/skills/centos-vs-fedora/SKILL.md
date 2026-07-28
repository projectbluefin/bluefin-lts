---
name: centos-vs-fedora
description: >-
  CentOS Stream 10 vs Fedora package and repo differences for bluefin-lts.
  Use when adding packages, enabling repos, choosing akmods tags, or resolving
  COPR chroot names.
---

# CentOS vs Fedora

bluefin-lts is built on **CentOS Stream 10**, not Fedora. Stock builds use the Fedora CoreOS stable kernel.

## What does not exist on CentOS Stream 10

| Fedora feature | CentOS equivalent |
|---|---|
| COPR CLI (`dnf copr enable`) | direct `.repo` URL only |
| `dnf5 copr` subcommand | not available |
| Fedora-versioned akmods tags | `ghcr.io/ublue-os/akmods-*:coreos-stable-<fedora_version>` |

## dnf vs dnf5 on CentOS Stream 10

CentOS Stream 10 ships **DNF4** (`/usr/bin/dnf`) as the default package manager.
**DNF5** (`/usr/bin/dnf5`) is available in the BaseOS repo but is NOT installed
by default and must be added explicitly to `build_scripts/packages/base.toml`.

DNF4 cannot expand `${releasever_minor:+-z}` in EPEL 10 metalink URLs, causing
HTTP 404 errors on `makecache`. DNF5 handles this correctly. Where this matters:

- `bluefin-lts-countme.service` calls `/usr/bin/dnf5 makecache` specifically to
  avoid the DNF4 metalink expansion bug (see `coreos/rpm-ostree#5464`). DNF5
  must be in the package list for this service to work.
- Build scripts (`build_scripts/`) use `dnf` (DNF4) throughout — this is correct
  for the build container context where metalink expansion is not an issue.

## What to use instead

- **Extra packages**: EPEL (`dnf install epel-release`).
- **COPR repos**: direct `dnf config-manager --add-repo <url>`.
- **Akmods**: use `coreos-stable-*` tags for the CoreOS stable kernel version.
- **Availability**: verify package names in CentOS/EPEL before adding them.

## COPR chroot naming

Most EL10-targeting COPR projects use the **`epel-10`** chroot, not `centos-stream-10`. Verify before hardcoding:

```bash
curl -s "https://copr.fedorainfracloud.org/api_3/project/search?query=OWNER/PROJECT" \
  | python3 -m json.tool | grep -A 10 chroot_repos
```

Typical URL pattern:

```bash
dnf config-manager --add-repo \
  "https://copr.fedorainfracloud.org/coprs/OWNER/PROJECT/repo/epel-10/OWNER-PROJECT-epel-10.repo"
```

## CI guard

`pr-testsuite.yml` blocks `copr enable` in `build_scripts/`. If CI fails for that reason, replace it with a direct repo URL.

## Common mistakes

- Copying `copr_install_isolated()` from Fedora bluefin scripts.
- Using `dnf5 copr enable`.
- Assuming `centos-stream-10` is the correct chroot.
- Using Fedora-version akmods tags directly.
- Assuming `dnf5` is installed in the runtime image — it must be listed explicitly in `base.toml`.

## When to Use

Use this skill before changing package, repository, COPR, or akmods inputs.

## When NOT to Use

Do not use it for workflow-only changes or release verification.

## Common Rationalizations

- “The Fedora recipe is close enough.” Verify the CentOS package and repository behavior.

## Red Flags

- `dnf copr enable`, unverified chroot names, or Fedora-only package flags.

## Verification

Confirm the repository URL, package availability, and applicable CI guard.
