#!/usr/bin/env python3
"""Audit the frozen V2 logical contract and FPGA five-plane DDR image.

This deliberately reports the compiled iCraft contract as PENDING until a real
generated JSON/RAW pair exists.  It never treats reference-test scales as final
NPU calibration scales.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
CONTRACT_PATH = Path(__file__).with_name("v2_tensor_contract.json")
RF_ROOT = WORKSPACE / "rf_cognitive_system"
ONNX_PATH = (
    RF_ROOT
    / "outputs/deployment_prep/time_power_phase/time_power_phase_npu_partition_opset17.onnx"
)
EXPORT_REPORT = (
    RF_ROOT / "outputs/deployment_prep/time_power_phase/deployment_export_report.json"
)
EXPECTED_CSV = RF_ROOT / "hardware/fpga/vectors/expected_core.csv"
EXPECTED_DDR = WORKSPACE / "pl_ddr_preparation/generated/expected_tensor_plddr.bin"
E2E_DDR = WORKSPACE / "pl_ddr_preparation/generated/e2e_tensor_plddr.bin"

FIELDS = ["iq_i_int8", "iq_q_int8", "power_int8", "lag_re_int8", "lag_im_int8"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fail(message: str) -> None:
    raise SystemExit(f"V2_TENSOR_CONTRACT_FAIL: {message}")


def pack_expected_csv(path: Path, frames: int, frame_length: int) -> bytes:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != frames * frame_length:
        fail(f"expected {frames * frame_length} CSV rows, found {len(rows)}")

    payload = bytearray(frames * len(FIELDS) * frame_length)
    for row_index, row in enumerate(rows):
        frame_id, sample_index = divmod(row_index, frame_length)
        if int(row["frame_id"]) != frame_id or int(row["sample_index"]) != sample_index:
            fail(f"CSV ordering error at row {row_index}")
        frame_base = frame_id * len(FIELDS) * frame_length
        for plane, field in enumerate(FIELDS):
            value = int(row[field])
            if not -128 <= value <= 127:
                fail(f"INT8 range error row={row_index} field={field} value={value}")
            payload[frame_base + plane * frame_length + sample_index] = value & 0xFF
    return bytes(payload)


def inspect_onnx(expected_inputs: dict[str, list[int]], expected_output: list[int]) -> dict:
    try:
        import onnx  # type: ignore
    except ImportError as exc:
        fail(f"onnx package is required for graph inspection: {exc}")

    model = onnx.load(str(ONNX_PATH))
    onnx.checker.check_model(model)

    def shape(value_info) -> list[int]:
        return [int(dim.dim_value) for dim in value_info.type.tensor_type.shape.dim]

    actual_inputs = {value.name: shape(value) for value in model.graph.input}
    actual_outputs = {value.name: shape(value) for value in model.graph.output}
    if actual_inputs != expected_inputs:
        fail(f"ONNX inputs differ: {actual_inputs!r}")
    if actual_outputs != {"logits": expected_output}:
        fail(f"ONNX outputs differ: {actual_outputs!r}")
    opsets = {item.domain: int(item.version) for item in model.opset_import}
    return {
        "checker": "PASS",
        "ir_version": int(model.ir_version),
        "opsets": opsets,
        "inputs": actual_inputs,
        "outputs": actual_outputs,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--compiled-dir",
        type=Path,
        default=Path(__file__).with_name("compiled_model"),
        help="directory expected to contain the final iCraft JSON/RAW pair",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path(__file__).with_name("audit_report.json"),
    )
    args = parser.parse_args()

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    export_report = json.loads(EXPORT_REPORT.read_text(encoding="utf-8"))
    frames = 19
    frame_length = int(contract["frame_length"])
    expected_size = frames * int(contract["frame_bytes"])

    actual_hash = sha256(ONNX_PATH)
    declared_hash = contract["source_model"]["sha256"]
    report_hash = export_report["npu_partition"]["sha256"]
    if actual_hash != declared_hash or actual_hash != report_hash:
        fail("ONNX SHA-256 does not match contract/export report")

    expected_inputs = {item["name"]: item["shape"] for item in contract["inputs"]}
    onnx_result = inspect_onnx(expected_inputs, contract["output"]["shape"])
    if onnx_result["ir_version"] != contract["source_model"]["onnx_ir_version"]:
        fail("ONNX IR version differs")
    if onnx_result["opsets"].get("") != contract["source_model"]["opset"]:
        fail("ONNX opset differs")

    csv_payload = pack_expected_csv(EXPECTED_CSV, frames, frame_length)
    expected_payload = EXPECTED_DDR.read_bytes()
    e2e_payload = E2E_DDR.read_bytes()
    if not (len(csv_payload) == len(expected_payload) == len(e2e_payload) == expected_size):
        fail("DDR payload size differs from 19 x 5 x 1024 bytes")
    if csv_payload != expected_payload:
        fail("expected_tensor_plddr.bin differs from expected_core.csv")
    if e2e_payload != expected_payload:
        fail("DDR/Core/DDR E2E output differs from Golden payload")

    json_files = sorted(args.compiled_dir.glob("*.json")) if args.compiled_dir.exists() else []
    raw_files = sorted(args.compiled_dir.glob("*.raw")) if args.compiled_dir.exists() else []
    compiled_status = "PRESENT_REQUIRES_RUNTIME_METADATA_AUDIT" if json_files and raw_files else "PENDING"

    result = {
        "logical_contract": "PASS",
        "fpga_reference_contract": "PASS",
        "ddr_core_ddr_e2e": "PASS_ZERO_MISMATCH",
        "onnx": onnx_result,
        "onnx_sha256": actual_hash,
        "tensor_ddr_bytes": expected_size,
        "tensor_ddr_sha256": sha256(E2E_DDR),
        "compiled_icraft_contract": compiled_status,
        "compiled_json": [str(path) for path in json_files],
        "compiled_raw": [str(path) for path in raw_files],
        "required_compiled_checks": [
            "two inputs with shapes [1,2,1024] and [1,3,1024]",
            "physical input layouts and contiguous byte sizes",
            "signed INT8 storage",
            "input scale(s) and zero-point(s)",
            "all operations assigned to ZG330 (no HostBackend fallback)",
        ],
    }
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("V2_TENSOR_LOGICAL_CONTRACT_PASS")
    print("DDR_CORE_DDR_E2E_GOLDEN_PASS mismatches=0 bytes=97280")
    print(f"COMPILED_ICRAFT_CONTRACT_{compiled_status}")
    print(f"report={args.report}")


if __name__ == "__main__":
    main()
