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
