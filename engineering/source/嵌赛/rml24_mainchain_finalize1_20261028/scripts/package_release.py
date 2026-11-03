#!/usr/bin/env python3
"""Create deterministic main-chain handoff ZIP and SHA manifests."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "rml24_mainchain_finalize1_20261028.zip"
EXCLUDE = {"SHA256SUMS.txt"}


def files() -> list[Path]:
    return sorted(
        path for path in ROOT.rglob("*")
        if path.is_file()
        and path.name not in EXCLUDE
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )


def main() -> int:
    selected = files()
    sums = []
    for path in selected:
        rel = path.relative_to(ROOT).as_posix()
        sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {rel}")
    manifest = ROOT / "SHA256SUMS.txt"
    manifest.write_text("\n".join(sums) + "\n", encoding="utf-8", newline="\n")
    selected.append(manifest)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(selected):
            rel = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"rml24_mainchain_finalize1_20261028/{rel}", (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    OUT.with_suffix(OUT.suffix + ".sha256").write_text(f"{digest}  {OUT.name}\n", encoding="ascii")
    print(f"PACKAGE_OK files={len(selected)} sha256={digest} path={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
