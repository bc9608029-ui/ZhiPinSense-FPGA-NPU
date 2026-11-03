"""Deterministic AutoDL package builder for the 24-class + OOD project.

Builds ``dist/sdr_amr_rml24_ood_v1_1_autodl_package.tar.gz`` with a fixed gzip/tar
mtime, owner 0, and a stable file ordering, then writes ``SHA256SUMS.txt`` inside
the archive.  Machine-local / regenerated artifacts (audit.json, the split
index .npz, manifests, training outputs) and the 20 GiB HDF5 are excluded; they
are regenerated on AutoDL by ``run_data_audit.sh``.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tarfile
from pathlib import Path
from typing import Iterator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "sdr_amr_rml24_ood_v1_1_autodl_package"
MTIME = 0

EXCLUDE_DIRS = {"__pycache__", ".git", ".pytest_cache", "runs", "exports", "dist",
                "outputs", "manifests", "build"}
EXCLUDE_SUFFIXES = {".pyc", ".hdf5", ".npz", ".pt", ".onnx"}
EXCLUDE_RELATIVE = {
    "data/radioml2018/audit.json",
    "data/radioml2018/rml24_split_indices.npz",
}


def iter_package_files(root: Path) -> Iterator[tuple[str, Path]]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.suffix.lower() in EXCLUDE_SUFFIXES:
            continue
        if str(rel).replace("\\", "/") in EXCLUDE_RELATIVE:
            continue
        if rel.name == "SHA256SUMS.txt":
            continue
        yield str(rel).replace("\\", "/"), path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_package(out_dir: Path, *, verify: bool = True) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"{PACKAGE_NAME}.tar.gz"

    files = list(iter_package_files(PROJECT_ROOT))
    if not files:
        raise RuntimeError("no package files matched; the exclusion list may be too broad")

    sums_lines: list[str] = []
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=MTIME) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for rel, path in files:
                    digest = sha256_file(path)
                    sums_lines.append(f"{digest}  {rel}\n")
                    info = tar.gettarinfo(str(path), arcname=f"{PACKAGE_NAME}/{rel}")
                    info.mtime = MTIME
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    with path.open("rb") as handle:
                        tar.addfile(info, handle)
                sums_blob = "".join(sorted(sums_lines)).encode("utf-8")
                sums_info = tarfile.TarInfo(name=f"{PACKAGE_NAME}/SHA256SUMS.txt")
                sums_info.size = len(sums_blob)
                sums_info.mtime = MTIME
                sums_info.uid = 0
                sums_info.gid = 0
                import io
                tar.addfile(sums_info, io.BytesIO(sums_blob))

    result: dict[str, object] = {
        "archive": str(archive),
        "archive_sha256": sha256_file(archive),
        "archive_size_bytes": archive.stat().st_size,
        "n_files": len(files) + 1,  # + SHA256SUMS.txt
    }
    if verify:
        verify_package(archive)
        result["verify"] = "ok"
    return result


def verify_package(archive: Path) -> None:
    import subprocess
    import sys
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(root, filter="data")
        base = root / PACKAGE_NAME
        manifest = sorted((base / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines())
        failures = 0
        for line in manifest:
            expected, _, rel = line.partition("  ")
            actual = sha256_file(base / rel)
            if actual != expected:
                failures += 1
                print(f"MISMATCH {rel}: expected {expected} got {actual}", file=sys.stderr)
        if failures:
            raise RuntimeError(f"package verification failed: {failures} mismatches")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="dist")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()
    result = build_package(Path(args.out_dir), verify=not args.no_verify)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
