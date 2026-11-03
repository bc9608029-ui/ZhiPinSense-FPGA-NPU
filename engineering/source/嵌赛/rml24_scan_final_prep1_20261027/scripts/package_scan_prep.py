#!/usr/bin/env python3
"""Build a deterministic, single-layer gzip delivery archive."""

from __future__ import annotations

import gzip
import hashlib
import io
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ARCHIVE = DIST / "rml24_scan_final_prep1_pc_ready.tar.gz"
OUTER_SUM = DIST / "rml24_scan_final_prep1_pc_ready.tar.gz.sha256"
PREFIX = ROOT.name
INCLUDE_DIRS = (
    "board_runtime",
    "contract",
    "deploy",
    "docs",
    "host_tests",
    "pc_runtime",
    "runtime",
    "scripts",
    "ui_overlay",
    "results",
)
INCLUDE_FILES = ("README.md",)


def selected_files() -> list[Path]:
    files = [ROOT / name for name in INCLUDE_FILES]
    for directory in INCLUDE_DIRS:
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files.append(path)
    files = [path for path in files if path != ARCHIVE and path != OUTER_SUM]
    return sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())


def normalized_info(name: str, size: int, mode: int = 0o644) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = mode
    # 1980-01-01 is deterministic and is also accepted by Windows tar/NTFS;
    # epoch 0 triggers noisy "Can't restore time" warnings on this workspace.
    info.mtime = 315532800
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def main() -> int:
    DIST.mkdir(parents=True, exist_ok=True)
    files = selected_files()
    sums = []
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}")
    sums_data = ("\n".join(sums) + "\n").encode("utf-8")

    with ARCHIVE.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for path in files:
                    relative = path.relative_to(ROOT).as_posix()
                    data = path.read_bytes()
                    mode = 0o755 if path.suffix in {".sh", ".py", ".ps1"} else 0o644
                    archive.addfile(normalized_info(f"{PREFIX}/{relative}", len(data), mode), io.BytesIO(data))
                archive.addfile(
                    normalized_info(f"{PREFIX}/SHA256SUMS.txt", len(sums_data)),
                    io.BytesIO(sums_data),
                )
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    OUTER_SUM.write_text(f"{digest}  {ARCHIVE.name}\n", encoding="ascii")
    print(f"PACKAGE_RESULT result=PASS files={len(files)} sha256={digest} bytes={ARCHIVE.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

