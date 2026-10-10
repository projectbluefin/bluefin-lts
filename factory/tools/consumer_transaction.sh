#!/usr/bin/env bash
# The GNOME transaction uses the candidate plus CentOS and EPEL, never COPR.
set -euo pipefail
# shellcheck source=factory/tools/dnf_retry.sh
source /repo/factory/tools/dnf_retry.sh
dnf -y install dnf-plugins-core
dnf config-manager --set-enabled crb
dnf -y install epel-release
printf '[factory]\nname=factory\nbaseurl=file:///factory\nenabled=1\ngpgcheck=0\npriority=1\n' > /etc/yum.repos.d/factory.repo
python3 - <<'PY' > /tmp/consumer-packages
import tomllib
with open('/repo/build_scripts/packages/base.toml', 'rb') as handle:
    manifest = tomllib.load(handle)
print('\n'.join(manifest['gnome']['packages']))
PY
mapfile -t packages < /tmp/consumer-packages
mapfile -t excluded < <(python3 /repo/build_scripts/scripts/read-packages \
    /repo/build_scripts/packages/base.toml gnome_excluded)
exclude_args=()
for package in "${excluded[@]}"; do exclude_args+=(-x "$package"); done
requested=("${packages[@]}" gnome50-el10-compat libgda \
    'gnome-shell >= 51.0' 'mutter >= 51.0' 'gdm >= 51.0' \
    'gnome-session >= 51.0' 'gnome-control-center >= 51.0' \
    'gnome-settings-daemon >= 51.0' 'gsettings-desktop-schemas >= 51.0')
dnf_retry -y --best install --downloadonly --downloaddir=/tmp/transaction \
    "${exclude_args[@]}" "${requested[@]}"
# Install the exact RPM set that passed the solve, without another repository
# query. This exercises scriptlets and proves the candidate can be installed.
dnf -y --disablerepo='*' install /tmp/transaction/*.rpm
python3 - <<'PY'
import subprocess
packages = ('gnome-shell', 'mutter', 'gdm', 'gnome-session',
            'gnome-control-center', 'gnome-settings-daemon',
            'gsettings-desktop-schemas')
for package in packages:
    version = subprocess.check_output(
        ['rpm', '-q', '--qf', '%{VERSION}', package], text=True).strip()
    print(f'Installed {package}: {version}', flush=True)
    if version.split('.')[0] != '51':
        raise SystemExit(f'{package}: expected GNOME 51, got {version}')
shell = subprocess.check_output(['gnome-shell', '--version'], text=True).strip()
print(shell, flush=True)
if not shell.startswith('GNOME Shell 51.'):
    raise SystemExit(f'Unexpected shell version: {shell}')
PY
