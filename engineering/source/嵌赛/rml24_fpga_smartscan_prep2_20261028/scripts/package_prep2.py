#!/usr/bin/env python3
"""Create deterministic FPGA smart-scan PREP2 handoff package."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "rml24_fpga_smartscan_prep2_20261028.zip"


def selected_files() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*")
        if p.is_file()
        and p.name != "SHA256SUMS.txt"
        and "__pycache__" not in p.parts
        and "xsim.dir" not in p.parts
        and "rundir" not in p.parts
        and ".Xil" not in p.parts
        and not any(part.startswith("work_") for part in p.parts)
        and p.suffix != ".pyc"
        and p.suffix not in {".jou", ".pb", ".wdb"}
        and p.name != "migration_console.log"
        and not (p.parent.name == "procise_target" and
                 p.suffix in {".fpe", ".edf", ".phy"})
        and not (p.parent.name == "procise_target" and
                 p.name in {"window_mul_q15.v", "fft_psd_stream_writer.v"})
        and not (p.parent == ROOT and (
            p.name.startswith("xsim") or p.name.startswith("xvlog")
            or p.name.startswith("xelab") or p.name.startswith("webtalk")
        ))
    )


def main() -> int:
    files = selected_files()
    manifest = ROOT / "SHA256SUMS.txt"
    manifest.write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}\n"
        for p in files
    ), encoding="utf-8", newline="\n")
    files.append(manifest)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(files):
            rel = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"rml24_fpga_smartscan_prep2_20261028/{rel}", (1980,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    OUT.with_suffix(OUT.suffix + ".sha256").write_text(f"{digest}  {OUT.name}\n", encoding="ascii")
    print(f"PACKAGE_OK files={len(files)} sha256={digest} path={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
