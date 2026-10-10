#!/usr/bin/env python3
"""Extract each recipe's BuildRequires by parsing it in the build root.

``rpmspec --parse`` resolves macros, conditionals and ``%files`` sections, so
the BuildRequires it reports are the ones rpmbuild will actually enforce. That
matters on EL10: a spec guards half its requirements behind ``%if 0%{?rhel}``,
and a regex over the spec text sees both branches.

This runs inside the pinned buildroot image rather than on the host, because
``rpmspec`` and the EL10 macro definitions are what make the answer correct.
The host has no rpm tooling and, if it did, different macros -- a build graph
solved against Fedora macros would order the EL10 stack wrongly.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.inventory import factory_root, inventory

SCRIPT = r"""#!/bin/bash
# Runs inside the build root. Args: <outdir>
set -euo pipefail
outdir="$1"
mkdir -p "$outdir"
dnf -y install rpm-build dnf-plugins-core redhat-rpm-config
dnf config-manager --set-enabled crb
dnf -y install epel-release
failed=0
for spec in /packages/*/*.spec; do
  name=$(basename "$(dirname "$spec")")
  if ! rpmspec --define "_sourcedir $(dirname "$spec")" --define "dist .el10" --parse "$spec" > "$outdir/$name.spec" 2> "$outdir/$name.err"; then
    echo "rpmspec failed for $name" >&2
    cat "$outdir/$name.err" >&2
    failed=1
  fi
  for query in names provides br; do
    if [ "$query" = names ]; then
      args=(--qf "%{NAME}\n")
    elif [ "$query" = provides ]; then
      args=(--provides)
    else
      args=(--buildrequires)
    fi
    if ! rpmspec -q "${args[@]}" --define "_sourcedir $(dirname "$spec")" \
        --define "dist .el10" "$spec" > "$outdir/$name.$query" 2>> "$outdir/$name.err"; then
      cat "$outdir/$name.err" >&2
      failed=1
    fi
  done
done
test "$failed" -eq 0
# Map generated capabilities from CentOS metadata back to source packages.
# This bootstraps pkgconfig/soname edges before a factory repo exists.
python3 - "$outdir" <<'PY'
import dnf, json, re, sys
from dnf.subject import Subject
from pathlib import Path
sys.path.insert(0, "/repo/factory")
from tools.build_graph import _requirement_names
from tools.assemble_repo import source_name
rows = Path(sys.argv[1])
requirements = set()
for br in rows.glob("*.br"):
    for line in br.read_text().splitlines():
        requirements.update(_requirement_names(line))
base = dnf.Base()
base.conf.read()
base.conf.substitutions.update_from_etc(base.conf.installroot, base.conf.varsdir)
base.read_all_repos()
base.fill_sack(load_system_repo=False)
provided = {}
for capability in sorted(requirements):
    for package in base.sack.query().available().filter(provides=capability):
        if package.sourcerpm:
            name = source_name(package.sourcerpm)
            provided.setdefault(name, set()).add(capability)
(rows / "base-providers.json").write_text(json.dumps({name: sorted(caps) for name, caps in provided.items()}))
# Keep exact version constraints, not just capability names. These witnesses
# may break bootstrap cycles only; the final DNF builddep still solves the
# entire transaction before compiling a recipe.
satisfied = {}
for br in rows.glob("*.br"):
    witnesses = {}
    for requirement in br.read_text().splitlines():
        if requirement.startswith("("):
            continue  # Rich dependencies need a transaction, not a name query.
        matches = Subject(requirement).get_best_query(base.sack).available()
        if matches:
            witnesses[requirement] = sorted(str(package) for package in matches)
    satisfied[br.stem] = witnesses
(rows / "base-satisfied.json").write_text(json.dumps(satisfied, indent=2))
PY
"""


def run(root: Path, image: str, output: Path, engine: str) -> None:
    """Execute the extractor inside the build root and collect the output."""
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = output / "rows"
    shutil.rmtree(rows, ignore_errors=True)
    rows.mkdir(parents=True, exist_ok=True)

    script = output / "extract.sh"
    script.write_text(SCRIPT)
    script.chmod(0o755)

    result = subprocess.run(
        [
            engine, "run", "--rm", "--pull=never",
            "-v", f"{root / 'packages'}:/packages:ro,Z",
            "-v", f"{root.parent}:/repo:ro,Z",
            "-v", f"{rows}:/out:Z",
            "-v", f"{script}:/extract.sh:ro,Z",
            image,
            "bash", "/extract.sh", "/out",
        ],
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            "extracting BuildRequires failed. A spec that will not parse cannot "
            "contribute graph edges, and skipping one would let it be scheduled "
            "into the first wave where it fails with no explanation."
        )

    if not any(rows.glob("*.spec")):
        raise SystemExit(
            f"{engine} produced no parsed specs from {image}. The packages volume "
            "did not mount, so the graph would come back empty and every package "
            "would land in wave 0."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--image", required=True, help="buildroot image reference")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engine", default="docker")
    args = parser.parse_args()

    root = factory_root(args.root)
    try:
        run(root, args.image, args.output, args.engine)
    except OSError as error:
        raise SystemExit(str(error)) from error

    parsed = len(list((args.output / "rows").glob("*.spec")))
    expected = len(inventory(root))
    print(json.dumps({"parsed": parsed, "recipes": expected}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
