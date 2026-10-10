#!/usr/bin/env python3
"""Build a computed CentOS wave plan without a fixed workflow depth limit.

Each recipe uses a fresh pinned container. Only earlier-wave successes enter
its dependency repository. Failures remain visible in the report and exit code;
independent recipes continue so one CI run gives useful diagnostics.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import subprocess
from pathlib import Path


def build_stack(plan: dict, repo: Path, image: str, engine: str, workers: int) -> int:
    work = repo / "work"
    prior, logs = work / "prior", work / "stack-logs"
    prior.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    report = {"packages": {}, "bootstrap": plan.get("bootstrap", [])}

    def build(package):
        env = dict(os.environ, PACKAGE=package)
        output = work / "rpms" / package
        shutil.rmtree(output, ignore_errors=True)
        output.mkdir(parents=True)
        with (logs / f"{package}.log").open("w") as log:
            stage = subprocess.run(
                ["python3", "factory/tools/source_pipeline.py", "stage", package],
                cwd=repo, stdout=log, stderr=subprocess.STDOUT, check=False)
            status = stage.returncode
            if not status:
                command = [engine, "run", "--rm", "--pull=never", "-e", "PACKAGE",
                           "-v", f"{repo}:/repo:Z", "-v", f"{prior}:/prior:Z",
                           image, "bash", "/repo/factory/tools/build_package.sh"]
                status = subprocess.run(command, env=env, stdout=log,
                                        stderr=subprocess.STDOUT, check=False).returncode
        rpms = sorted(output.glob("*.rpm"))
        if not status and not rpms:
            status = 1
        if status:
            # A partial output from a failed build is never a dependency.
            shutil.rmtree(output)
            print(f"FAIL {package}:\n" + (logs / f"{package}.log").read_text()[-5000:], flush=True)
        else:
            print(f"OK {package}: {len(rpms)} RPMs", flush=True)
        return package, {"status": status, "rpms": [p.name for p in rpms] if not status else []}

    for stage, packages in enumerate(plan["waves"]):
        print(f"Wave {stage}: {', '.join(packages)}", flush=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            for package, result in pool.map(build, packages):
                report["packages"][package] = dict(result, wave=stage)
        for package in packages:
            if not report["packages"][package]["status"]:
                for rpm in (work / "rpms" / package).glob("*.rpm"):
                    shutil.copy2(rpm, prior / rpm.name)
        (work / "stack-report.json").write_text(json.dumps(report, indent=2) + "\n")
        # Save disk after each wave; RPMs and logs are retained as evidence.
        cleanup = subprocess.run(
            [engine, "run", "--rm", "--pull=never", "-v", f"{repo}:/repo:Z",
             image, "rm", "-rf", "/repo/work/rpmbuild"], check=False)
        if cleanup.returncode:
            raise RuntimeError("could not clean root-owned RPM build trees")
    return int(any(result["status"] for result in report["packages"].values()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--image", default="factory-buildroot:run")
    parser.add_argument("--engine", default="docker")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    raise SystemExit(build_stack(json.loads(args.plan.read_text()), args.repo.resolve(),
                                 args.image, args.engine, args.workers))
