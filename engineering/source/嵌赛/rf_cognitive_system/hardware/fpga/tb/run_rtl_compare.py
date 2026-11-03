"""Run available Icarus RTL tests and compare their CSV output to Python.

The script exits successfully with an explicit SKIPPED result when Icarus is
not installed.  It never substitutes Python output for an RTL simulation.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess


FPGA_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = FPGA_ROOT.parents[1]
RESULTS = FPGA_ROOT / "tb" / "results"


def _run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _compare_columns(actual_path: Path, expected_path: Path, columns: list[str]) -> int:
    actual = _read_csv(actual_path)
    expected = _read_csv(expected_path)
    if len(actual) != len(expected):
        raise AssertionError(f"row count differs: RTL={len(actual)} Python={len(expected)}")
    mismatches = 0
    for row_index, (rtl_row, python_row) in enumerate(zip(actual, expected, strict=True)):
        for column in columns:
            if int(rtl_row[column]) != int(python_row[column]):
                mismatches += 1
                if mismatches <= 10:
                    print(
                        f"mismatch row={row_index} column={column} "
                        f"rtl={rtl_row[column]} python={python_row[column]}"
                    )
    if mismatches:
        raise AssertionError(f"{mismatches} RTL/Python element mismatches")
    return len(actual) * len(columns)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-simulator", action="store_true")
    args = parser.parse_args()
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not iverilog or not vvp:
        result = {
            "status": "SKIPPED",
            "reason": "iverilog/vvp not found",
            "rtl_simulated": False,
            "python_substitution_used": False,
        }
        print(json.dumps(result, indent=2))
        if args.require_simulator:
            raise SystemExit(2)
        return

    RESULTS.mkdir(parents=True, exist_ok=True)
    rtl = FPGA_ROOT / "rtl"
    tb = FPGA_ROOT / "tb"
    common_sources = [
        rtl / "common" / "iq_stream_fifo.sv",
        rtl / "framing" / "iq_frame_controller.sv",
        rtl / "features" / "qam_feature_pipeline.sv",
        rtl / "quantization" / "feature_quantizer.sv",
        rtl / "tensor" / "tensor_packer.sv",
        rtl / "common" / "mandatory_core_path.sv",
    ]
    simulations = [
        ("fifo", [rtl / "common" / "iq_stream_fifo.sv", tb / "unit" / "tb_iq_stream_fifo.sv"]),
        ("quantizer", [rtl / "quantization" / "feature_quantizer.sv", tb / "unit" / "tb_feature_quantizer.sv"]),
        ("framer", [rtl / "framing" / "iq_frame_controller.sv", tb / "unit" / "tb_iq_frame_controller.sv"]),
        ("packer", [rtl / "tensor" / "tensor_packer.sv", tb / "unit" / "tb_tensor_packer.sv"]),
        ("features", [rtl / "features" / "qam_feature_pipeline.sv", tb / "integration" / "tb_qam_feature_vectors.sv"]),
        ("core", [*common_sources, tb / "integration" / "tb_mandatory_core.sv"]),
    ]
    for name, sources in simulations:
        executable = RESULTS / f"{name}.vvp"
        command = [iverilog, "-g2012", "-I", str(FPGA_ROOT / "vectors"), "-o", str(executable)]
        command.extend(str(source) for source in sources)
        _run(command, FPGA_ROOT)
        _run([vvp, str(executable)], FPGA_ROOT)

    expected = FPGA_ROOT / "vectors" / "expected_core.csv"
    checked = 0
    checked += _compare_columns(
        RESULTS / "rtl_features.csv", expected, ["frame_id", "sample_index", "power", "lag_re", "lag_im"]
    )
    checked += _compare_columns(
        RESULTS / "rtl_core.csv",
        expected,
        [
            "frame_id", "sample_index", "iq_i_int8", "iq_q_int8", "power_int8",
            "lag_re_int8", "lag_im_int8", "iq_i_addr", "iq_q_addr", "power_addr",
            "lag_re_addr", "lag_im_addr",
        ],
    )
    print(json.dumps({"status": "PASS", "rtl_simulated": True, "elements_checked": checked}, indent=2))


if __name__ == "__main__":
    main()
