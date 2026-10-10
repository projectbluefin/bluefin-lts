#!/usr/bin/env python3
"""Generate an offline cargo vendor bundle from a verified upstream Cargo.lock.

Adapted from projectbluefin/utah-packages tools/generated_sources.py. Every
registry archive is verified against Cargo.lock; git sources are refused.
The deterministic output is independently SHA-512 locked before builds.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import io
import json
import tarfile
from pathlib import Path, PurePosixPath

CRATES_IO_INDEX = "registry+https://github.com/rust-lang/crates.io-index"
CRATE_URL = "https://static.crates.io/crates/{name}/{name}-{version}.crate"

def cargo_lock_packages(lock_text: str) -> list[dict]:
    """The crates.io packages a Cargo.lock pins, with their SHA-256 checksums.

    Cargo.lock is TOML; tomllib is standard library from Python 3.11. Anything
    not from crates.io (git or path sources) is refused: the vendored bundle
    must be reproducible from checksum-pinned registry downloads alone. The
    workspace root itself has no source and is skipped.
    """
    import tomllib

    crates = []
    for package in tomllib.loads(lock_text).get("package", []):
        source = package.get("source")
        if source is None:
            continue
        if source != CRATES_IO_INDEX:
            raise RuntimeError(f"{package['name']} {package['version']} comes from {source}, not crates.io")
        if not package.get("checksum"):
            raise RuntimeError(f"{package['name']} {package['version']} has no checksum in Cargo.lock")
        crates.append({"name": package["name"], "version": package["version"], "checksum": package["checksum"]})
    return sorted(crates, key=lambda crate: (crate["name"], crate["version"]))


def _vendored_crate_members(crate: dict, payload: bytes, prefix: str, mtime: int):
    """Yield (TarInfo, bytes) for one crate laid out as `cargo vendor --versioned-dirs` does.

    The .crate is checked against the Cargo.lock checksum first, so crates.io
    cannot substitute bytes. .cargo-checksum.json lists every file's SHA-256
    and the package checksum, which is what a cargo directory source verifies.
    """
    actual = hashlib.sha256(payload).hexdigest()
    if actual != crate["checksum"]:
        raise RuntimeError(f"crate {crate['name']} {crate['version']}: expected sha256 {crate['checksum']}, got {actual}")
    top = f"{crate['name']}-{crate['version']}"
    directory = f"{prefix}/{top}"
    contents: dict[str, bytes] = {}
    executable: set[str] = set()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as source:
        for member in source.getmembers():
            if not member.isreg():
                continue
            if not member.name.startswith(top + "/"):
                raise RuntimeError(f"crate {top} has a member outside its directory: {member.name}")
            relative = member.name[len(top) + 1:]
            if PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(relative).parts:
                raise RuntimeError(f"crate {top} has an unsafe path: {member.name}")
            if relative == ".cargo-checksum.json":  # regenerated below
                continue
            contents[relative] = source.extractfile(member).read()
            if member.mode & 0o111:
                executable.add(relative)
    checksum = {
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(contents.items())},
        "package": crate["checksum"],
    }
    contents[".cargo-checksum.json"] = json.dumps(checksum, sort_keys=True, separators=(",", ":")).encode()
    directories = {directory}
    for relative in contents:
        parts = relative.split("/")[:-1]
        for index in range(1, len(parts) + 1):
            directories.add(f"{directory}/{'/'.join(parts[:index])}")
    for name in sorted(directories):
        info = tarfile.TarInfo(name)
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        info.mtime = mtime
        yield info, None
    for relative, data in sorted(contents.items()):
        info = tarfile.TarInfo(f"{directory}/{relative}")
        info.size = len(data)
        info.mode = 0o755 if relative in executable else 0o644
        info.mtime = mtime
        yield info, data


def generate(archive: Path, output: Path, lockfile: str = "Cargo.lock") -> Path:
    from tools.source_pipeline import _fetch
    relative = PurePosixPath(lockfile)
    if relative.is_absolute() or ".." in relative.parts or relative.name != "Cargo.lock":
        raise ValueError("vendor lockfile must be a relative Cargo.lock path")
    with tarfile.open(archive) as source:
        members = [m for m in source.getmembers()
                   if m.isfile() and m.name.partition("/")[2] == str(relative)]
        if len(members) != 1:
            raise ValueError(f"upstream archive must contain one {lockfile}")
        crates = cargo_lock_packages(source.extractfile(members[0]).read().decode())
    cache = output.parent / ".crate-cache"
    cache.mkdir(exist_ok=True)

    def fetch(crate):
        path = cache / (crate["name"] + "-" + crate["version"] + ".crate")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != crate["checksum"]:
            payload = _fetch(CRATE_URL.format(**crate))
            if hashlib.sha256(payload).hexdigest() != crate["checksum"]:
                raise ValueError(f"crate checksum mismatch: {path.name}")
            path.write_bytes(payload)
        return path

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        paths = list(pool.map(fetch, crates))
    with tarfile.open(output, "w:xz", format=tarfile.PAX_FORMAT, preset=6) as target:
        info = tarfile.TarInfo("vendor")
        info.type, info.mode, info.mtime = tarfile.DIRTYPE, 0o755, 0
        target.addfile(info)
        for crate, path in zip(crates, paths):
            for info, data in _vendored_crate_members(crate, path.read_bytes(), "vendor", 0):
                target.addfile(info, io.BytesIO(data) if data is not None else None)
    return output


if __name__ == "__main__":
    import argparse
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--lockfile", default="Cargo.lock")
    args = parser.parse_args()
    path = generate(args.archive, args.output, args.lockfile)
    print(hashlib.sha512(path.read_bytes()).hexdigest(), path)
