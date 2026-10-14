#!/usr/bin/env python3
"""Load and select recipe-scoped container policies, retaining engine capabilities."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.inventory import factory_root


def apparmor_enabled(engine: str = 'docker') -> bool:
    # A loaded host module does not imply that the container engine supports
    # AppArmor (notably Podman builds without that feature).
    podman = Path(engine).name == 'podman'
    field = '{{json .Host.Security}}' if podman else '{{json .SecurityOptions}}'
    output = subprocess.check_output([engine, 'info', '--format', field], text=True).strip()
    data = json.loads(output)
    return data['apparmorEnabled'] if podman else 'name=apparmor' in data


def security_args(root: Path, package: str, engine: str = 'docker') -> list[str]:
    directory = root / 'packages' / package
    args = []
    seccomp = directory / f'{package}-seccomp.json'
    if seccomp.is_file():
        args += ['--security-opt', f'seccomp={seccomp}']
    if (directory / f'{package}.apparmor').is_file() and apparmor_enabled(engine):
        args += ['--security-opt', f'apparmor=bluefin-factory-{package}']
    return args


def load(root: Path, package: str | None = None, engine: str = 'docker') -> None:
    if not apparmor_enabled(engine):
        return
    profiles = ([root / 'packages' / package / f'{package}.apparmor'] if package
                else sorted((root / 'packages').glob('*/*.apparmor')))
    for profile in profiles:
        if profile.is_file():
            subprocess.run(['sudo', '-n', 'apparmor_parser', '-r', '-T', str(profile)], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('load', 'args'))
    parser.add_argument('--root', type=Path)
    parser.add_argument('--package')
    parser.add_argument('--engine', default='docker')
    args = parser.parse_args()
    root = factory_root(args.root)
    if args.command == 'load':
        load(root, args.package, args.engine)
    elif not args.package:
        parser.error('args requires --package')
    else:
        sys.stdout.write(''.join(f'{argument}\n' for argument in security_args(root, args.package, args.engine)))
