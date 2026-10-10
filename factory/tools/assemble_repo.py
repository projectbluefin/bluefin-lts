#!/usr/bin/env python3
"""Replace successful source builds, keeping failed recipes' previous RPMs.

Adapted from utah-packages' incremental publication: a build list describes
attempts, while the new RPM headers describe what can actually replace a seed.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def source_name(sourcerpm: str) -> str:
    if not sourcerpm.endswith('.src.rpm'):
        raise ValueError(f'invalid source RPM: {sourcerpm!r}')
    parts = sourcerpm.removesuffix('.src.rpm').rsplit('-', 2)
    if len(parts) != 3 or not all(parts):
        raise ValueError(f'invalid source RPM: {sourcerpm!r}')
    return parts[0]


def rpm_source(path: Path) -> str:
    result = subprocess.run(['rpm', '-qp', '--qf', '%{SOURCERPM}', str(path)],
                            capture_output=True, text=True, check=True)
    return source_name(result.stdout.strip())


def assemble(seed: Path, built: Path, selected: set[str]) -> set[str]:
    new = {rpm: rpm_source(rpm) for rpm in sorted(built.rglob('*.rpm'))
           if not rpm.name.endswith(('.src.rpm', '.nosrc.rpm'))}
    replaced = set(new.values())
    if unexpected := replaced - selected:
        raise ValueError('unexpected source packages: ' + ', '.join(sorted(unexpected)))
    # Query everything before deleting anything: a corrupt RPM must fail the
    # assembly instead of quietly leaving duplicate or stale subpackages.
    old = {rpm: rpm_source(rpm) for rpm in sorted(seed.rglob('*.rpm'))}
    for rpm, source in old.items():
        if source in replaced:
            rpm.unlink()
    seed.mkdir(parents=True, exist_ok=True)
    for rpm in new:
        shutil.copy2(rpm, seed / rpm.name)
    return replaced


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=Path, required=True)
    parser.add_argument('--built', type=Path, required=True)
    parser.add_argument('--build-list', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    replaced = assemble(args.seed, args.built, set(json.loads(args.build_list)))
    args.report.write_text(json.dumps(sorted(replaced)) + '\n')
    print(f'replaced {len(replaced)} successful source builds')


if __name__ == '__main__':
    main()
