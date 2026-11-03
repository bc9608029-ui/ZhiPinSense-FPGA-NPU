#!/usr/bin/env python3
"""Build a deterministic single-layer gzip deployment archive."""

from __future__ import annotations

import gzip
import hashlib
import io
import os
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ARCHIVE = DIST / "rml24_final_integration1_pcprep.tar.gz"
SUM_FILE = DIST / "rml24_final_integration1_pcprep_SHA256.txt"
INCLUDE_DIRS = ("board_runtime", "contract", "deploy", "docs", "recovery", "runtime", "scripts", "evidence")
TAR_MTIME = 315532800  # 1980-01-01: deterministic and representable by Windows tar


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def included_files() -> list[Path]:
    paths = [ROOT / "README.md"]
    for directory in INCLUDE_DIRS:
        base = ROOT / directory
        if not base.is_dir():
            continue
        paths.extend(
            path for path in base.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".gz"}
        )
    return sorted(paths, key=lambda path: path.relative_to(ROOT).as_posix())


def tar_bytes() -> bytes:
    files = included_files()
    sums = "".join(f"{digest(path.read_bytes())}  {path.relative_to(ROOT).as_posix()}\n" for path in files).encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in files:
            name = Path("rml24_final_integration1") / path.relative_to(ROOT)
            info = archive.gettarinfo(str(path), arcname=name.as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = TAR_MTIME
            with path.open("rb") as handle:
                archive.addfile(info, handle)
        info = tarfile.TarInfo("rml24_final_integration1/SHA256SUMS.txt")
        info.size = len(sums)
        info.mode = 0o644
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mtime = TAR_MTIME
        archive.addfile(info, io.BytesIO(sums))
    return buffer.getvalue()


def build() -> tuple[str, int]:
    raw_tar = tar_bytes()
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0, compresslevel=9) as zipped:
        zipped.write(raw_tar)
    data = output.getvalue()
    DIST.mkdir(parents=True, exist_ok=True)
    ARCHIVE.write_bytes(data)
    archive_sha = digest(data)
    SUM_FILE.write_text(f"{archive_sha}  {ARCHIVE.name}\n", encoding="ascii", newline="\n")
    return archive_sha, len(data)


if __name__ == "__main__":
    first_sha, size = build()
    first_bytes = ARCHIVE.read_bytes()
    second_sha, second_size = build()
    if first_sha != second_sha or first_bytes != ARCHIVE.read_bytes() or size != second_size:
        raise SystemExit("deterministic rebuild failed")
    print(f"RML24_FINAL_PACKAGE result=PASS sha256={second_sha} bytes={second_size} members={len(included_files()) + 1}")

