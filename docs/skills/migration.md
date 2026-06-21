---
name: bluefin-lts-migration
description: >-
  Complete implementation spec for the ublue-os/bluefin → projectbluefin/bluefin-lts user
  migration service. Use when implementing the migration service in ublue-os/bluefin so
  existing LTS users are automatically moved to the new image on next reboot.
metadata:
  type: runbook
---

# ublue-os/bluefin LTS migration service — implementation spec

## Purpose

Users currently on `ghcr.io/ublue-os/bluefin*:lts` must be moved to the new home at
`ghcr.io/projectbluefin/bluefin-lts*:lts`. This is done by shipping a one-shot systemd
timer + service + script in the **old** `ublue-os/bluefin` image. The service runs
`bootc switch` non-destructively; the user lands on the new image after their next reboot.

This spec targets an agent working in the **`ublue-os/bluefin`** repo. Everything below
describes files to create/modify in that repo.

---

## Variant mapping (old → new)

| Old image (ublue-os) | New image (projectbluefin) | Notes |
|---|---|---|
| `ghcr.io/ublue-os/bluefin-gdx:lts*` | `ghcr.io/projectbluefin/bluefin-lts-hwe-nvidia:lts` | dx/gdx users: `ujust devmode` after reboot |
| `ghcr.io/ublue-os/bluefin-dx:lts-hwe*` | `ghcr.io/projectbluefin/bluefin-lts-hwe:lts` | dx users: `ujust devmode` after reboot |
| `ghcr.io/ublue-os/bluefin-dx:lts*` | `ghcr.io/projectbluefin/bluefin-lts:lts` | dx users: `ujust devmode` after reboot |
| `ghcr.io/ublue-os/bluefin:lts-hwe*` | `ghcr.io/projectbluefin/bluefin-lts-hwe:lts` | |
| `ghcr.io/ublue-os/bluefin:lts*` (incl. GNOME50) | `ghcr.io/projectbluefin/bluefin-lts:lts` | |
| arm64 variants | MOTD notice only, no automatic switch | reinstall from new image |

---

## Files to create in ublue-os/bluefin

The `ublue-os/bluefin` repo uses `files/` for system files (equivalent to `system_files/`
in this repo) and `build_files/` for build scripts (equivalent to `build_scripts/` here).

```
files/usr/lib/systemd/system/bluefin-lts-migrate.service
files/usr/lib/systemd/system/bluefin-lts-migrate.timer
files/usr/libexec/bluefin-lts-migrate
```

---

## File contents

### `files/usr/libexec/bluefin-lts-migrate`

```bash
#!/usr/bin/env bash
# Migrate the machine from ublue-os/bluefin:lts to projectbluefin/bluefin-lts.
# Runs as a one-shot service; retries daily until success.
set -euo pipefail

STAMP="/etc/bluefin-lts-migrated"
MOTD="/etc/motd.d/50-bluefin-lts-migration"

# Already migrated
[[ -f "${STAMP}" ]] && exit 0

# Read current image reference
CURRENT_IMAGE="$(python3 -c "
import json, sys
data = json.load(sys.stdin)
spec = data.get('spec', {}) or {}
image = spec.get('image', {}) or {}
print(image.get('image', ''))
" <<< "$(bootc status --format=json)")"

# Already on the new registry
if [[ "${CURRENT_IMAGE}" == *"projectbluefin"* ]]; then
    touch "${STAMP}"
    exit 0
fi

# arm64: unsupported for automatic migration
if [[ "$(uname -m)" == "aarch64" ]]; then
    mkdir -p /etc/motd.d
    cat > "${MOTD}" <<'EOF'
Bluefin LTS has moved to a new home.
Automatic migration is not available for arm64.
Please reinstall from the new image:
  https://projectbluefin.io
EOF
    exit 0
fi

# Map variant to new image
DX_NOTE=""
case "${CURRENT_IMAGE}" in
    *bluefin-gdx*)
        NEW_IMAGE="ghcr.io/projectbluefin/bluefin-lts-hwe-nvidia:lts"
        DX_NOTE="Run 'ujust devmode' after reboot to restore developer tools."
        ;;
    *bluefin-dx*lts-hwe* | *bluefin-dx*hwe*)
        NEW_IMAGE="ghcr.io/projectbluefin/bluefin-lts-hwe:lts"
        DX_NOTE="Run 'ujust devmode' after reboot to restore developer tools."
        ;;
    *bluefin-dx*)
        NEW_IMAGE="ghcr.io/projectbluefin/bluefin-lts:lts"
        DX_NOTE="Run 'ujust devmode' after reboot to restore developer tools."
        ;;
    *bluefin*lts-hwe* | *bluefin*hwe*)
        NEW_IMAGE="ghcr.io/projectbluefin/bluefin-lts-hwe:lts"
        ;;
    *)
        NEW_IMAGE="ghcr.io/projectbluefin/bluefin-lts:lts"
        ;;
esac

# Write pre-reboot MOTD
mkdir -p /etc/motd.d
{
    echo ""
    echo "Bluefin LTS is moving to its new home."
    echo "Your machine will switch to ${NEW_IMAGE} on next reboot."
    [[ -n "${DX_NOTE}" ]] && echo "${DX_NOTE}"
    echo ""
} > "${MOTD}"

# Stage the switch (non-destructive until reboot)
if bootc switch --enforce-container-sigpolicy "${NEW_IMAGE}"; then
    touch "${STAMP}"
    systemctl disable bluefin-lts-migrate.timer || true
else
    # Append retry note; service exits 1 so timer retries tomorrow
    echo "(Migration will retry automatically. Check 'journalctl -u bluefin-lts-migrate' for details.)" >> "${MOTD}"
    exit 1
fi
```

### `files/usr/lib/systemd/system/bluefin-lts-migrate.service`

```ini
[Unit]
Description=Migrate from ublue-os/bluefin LTS to projectbluefin/bluefin-lts
After=network-online.target bootc.service
Wants=network-online.target
ConditionPathExists=!/etc/bluefin-lts-migrated

[Service]
Type=oneshot
ExecStart=/usr/libexec/bluefin-lts-migrate
RemainAfterExit=no
```

### `files/usr/lib/systemd/system/bluefin-lts-migrate.timer`

```ini
[Unit]
Description=Daily retry for Bluefin LTS migration
After=network-online.target

[Timer]
OnBootSec=2min
OnUnitInactiveSec=24h
Unit=bluefin-lts-migrate.service

[Install]
WantedBy=timers.target
```

---

## Build enablement

In `ublue-os/bluefin`, find the build script that enables systemd services (typically
`build_files/40-services.sh` or similar). Add:

```bash
systemctl enable bluefin-lts-migrate.timer
```

Also ensure the migration script is executable. Add to the same script or a Containerfile
`RUN` step:

```bash
chmod +x /usr/libexec/bluefin-lts-migrate
```

If services are enabled in the Containerfile directly, add:

```dockerfile
RUN systemctl enable bluefin-lts-migrate.timer && \
    chmod +x /usr/libexec/bluefin-lts-migrate
```

---

## Signing policy — no changes required

Both `ghcr.io/ublue-os/bluefin:lts` and `ghcr.io/projectbluefin/bluefin-lts:lts` ship the
same `policy.json` from `projectbluefin/common`. `ghcr.io/projectbluefin` is not listed
explicitly and falls through to the `""` catch-all (`insecureAcceptAnything`). The
`bootc switch --enforce-container-sigpolicy` call in the migration script succeeds without
any policy.json edits.

Verified 2026-06-21 against both images via ghost lab podman headless test.

---

## Testing the migration

### Fast: podman headless (variant mapping only)

Run the migration script inside the real old image to verify variant detection and MOTD
content — mock `bootc switch` so no actual switch happens.

```bash
podman run --rm \
  -v ./bluefin-lts-migrate:/usr/libexec/bluefin-lts-migrate:ro \
  ghcr.io/ublue-os/bluefin:lts \
  bash -c '
    mkdir -p /tmp/bin
    echo "#!/bin/bash" > /tmp/bin/bootc
    echo "echo DRYRUN: \$@" >> /tmp/bin/bootc
    chmod +x /tmp/bin/bootc
    export PATH=/tmp/bin:$PATH
    /usr/libexec/bluefin-lts-migrate
    echo "--- MOTD ---"
    cat /etc/motd.d/50-bluefin-lts-migration 2>/dev/null || echo "(no motd)"
  '
```

For multi-variant coverage, use the Argo DAG pattern in `docs/skills/testing.md`.
All 5 variants were smoke-tested on 2026-06-21 — see testing.md for results.

### Full: KubeVirt VM (end-to-end reboot verification)

Required to verify that:
- `bootc switch` actually stages the new image
- Machine boots into `projectbluefin/bluefin-lts:lts` after reboot
- Timer fires correctly at boot
- No failed systemd units in the post-migration journal

Use the `lab-test` skill to boot the old image in a KubeVirt VM, then trigger the migration
service manually (`systemctl start bluefin-lts-migrate`) and reboot.

---

## Checklist for the ublue-os/bluefin agent

Before opening a PR in `ublue-os/bluefin`:

- [ ] `files/usr/libexec/bluefin-lts-migrate` created and marked executable
- [ ] `files/usr/lib/systemd/system/bluefin-lts-migrate.service` created
- [ ] `files/usr/lib/systemd/system/bluefin-lts-migrate.timer` created
- [ ] `systemctl enable bluefin-lts-migrate.timer` added to the services build script
- [ ] `chmod +x /usr/libexec/bluefin-lts-migrate` added (or confirmed applied)
- [ ] Podman headless smoke test passed against `ghcr.io/ublue-os/bluefin:lts`
- [ ] MOTD content verified for each variant (base, hwe, dx, dx-hwe, gdx)
- [ ] `ujust devmode` note present in MOTD for dx and gdx variants

---

## See also

- `docs/skills/ci-cd.md` — signing policy details, ghost lab migration workflow notes,
  and why the existing Argo migration templates are NOT suitable for LTS migration testing
- `docs/skills/testing.md` — podman headless Argo workflow template and multi-variant DAG
  pattern; real lts-migration-smoke results from 2026-06-21
