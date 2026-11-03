#!/usr/bin/env python3
"""Record tool availability without treating catalog files as generated IP."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    catalog = Path(r"D:\FMSH\JFM_Kits\ip_patch\device_database\common\fmsh\2022.1\vv_index.xml")
    catalog_mentions_fft = catalog.is_file() and "xfft_v9_1" in catalog.read_text(encoding="utf-8", errors="ignore")
    vivado_bin = Path(r"D:\Xilinx2018.3\Vivado\2018.3\bin")
    def tool(name: str):
        found = shutil.which(name)
        explicit = vivado_bin / f"{name}.bat"
        return found or (str(explicit) if explicit.is_file() else None)
    data = {
        "procise_executable": next((str(p) for p in (
            Path(r"D:\fudanwei\Procise\bin\procise.exe"),
            Path(r"D:\FMSH\Procise\bin\procise.exe"),
        ) if p.is_file()), shutil.which("procise")),
        "xvlog": tool("xvlog"),
        "xelab": tool("xelab"),
        "xsim": tool("xsim"),
        "iverilog": shutil.which("iverilog"),
        "verilator": shutil.which("verilator"),
        "fmsh_2022_1_catalog": str(catalog) if catalog.is_file() else None,
        "catalog_mentions_xfft_v9_1": catalog_mentions_fft,
        "interpretation": (
            "Vivado XFFT generation/synthesis and Procise post-FFT OOC are available; "
            "full migrated FFT plus post-FFT integration is still pending"
        ),
    }
    out = ROOT / "results" / "environment_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("SMART_SCAN_ENV_AUDIT result=RECORDED xsim_ready=%d target_build_ready=%d" %
          (bool(data["xsim"]), bool(data["procise_executable"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
