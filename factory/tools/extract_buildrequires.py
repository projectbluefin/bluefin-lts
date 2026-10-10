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
failed=0
for spec in /packages/*/*.spec; do
  name=$(basename "$(dirname "$spec")")
  if ! rpmspec --parse "$spec" > "$outdir/$name.spec" 2> "$outdir/$name.err"; then
    echo "rpmspec failed for $name" >&2
    cat "$outdir/$name.err" >&2
    failed=1
  fi
  rm -f "$outdir/$name.err"
done
exit "$failed"
"""


def run(root: Path, image: str, output: Path, engine: str) -> None:
    """Execute the extractor inside the build root and collect the output."""
    output.mkdir(parents=True, exist_ok=True)
    rows = output / "rows"
    shutil.rmtree(rows, ignore_errors=True)
    rows.mkdir(parents=True, exist_ok=True)

    script = output / "extract.sh"
    script.write_text(SCRIPT)
    script.chmod(0o755)

    result = subprocess.run(
        [
            engine, "run", "--rm",
            "-v", f"{root / 'packages'}:/packages:ro,Z",
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