"""Export and audit the frozen TimePowerPhase deployment candidate.

Two graphs are emitted:
1. an end-to-end PC reference graph that computes Power/Lag-1 internally;
2. the planned NPU partition with explicit FPGA-produced physical features.

The script never constructs or reads final_blind_test samples.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import onnx
import torch

from deployment.time_power_phase_partition import (
    TimePowerPhaseNPUPartition,
    external_physical_features,
    load_formal_candidate,
)
from training.qam_aware_utils import load_qam_aware_config
from training.utils import resolve_project_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _shape(value: onnx.ValueInfoProto) -> list[int | str]:
    dimensions: list[int | str] = []
    for dimension in value.type.tensor_type.shape.dim:
        dimensions.append(dimension.dim_value if dimension.HasField("dim_value") else dimension.dim_param)
    return dimensions


def _inspect(path: Path) -> dict[str, Any]:
    graph = onnx.load(path)
    onnx.checker.check_model(graph)
    initializers = {item.name for item in graph.graph.initializer}
    inputs = [item for item in graph.graph.input if item.name not in initializers]
    return {
        "checker_passed": True,
        "opset": max(item.version for item in graph.opset_import),
        "op_types": dict(sorted(Counter(node.op_type for node in graph.graph.node).items())),
        "inputs": {item.name: _shape(item) for item in inputs},
        "outputs": {item.name: _shape(item) for item in graph.graph.output},
        "file_size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def export_candidate(
    config_path: str,
    checkpoint_path: str,
    output_dir: str,
) -> dict[str, Any]:
    config = load_qam_aware_config(config_path)
    sample_length = int(config["signal"]["sample_length"])
    classes = list(config["signal"]["modulations"])
    checkpoint = resolve_project_path(checkpoint_path)
    destination = resolve_project_path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    model, checkpoint_data = load_formal_candidate(config_path, checkpoint)
    partition = TimePowerPhaseNPUPartition(model).eval()
    generator = torch.Generator().manual_seed(2026)
    iq = torch.randn(1, 2, sample_length, generator=generator, dtype=torch.float32) * 0.25
    physical = external_physical_features(model, iq)
    with torch.inference_mode():
        reference_logits = model(iq)
        partition_logits = partition(iq, physical)
    parity_error = float(torch.max(torch.abs(reference_logits - partition_logits)).item())
    if parity_error > 1e-6:
        raise RuntimeError(f"Partition parity failed: max_abs_error={parity_error}")

    end_to_end_path = destination / "time_power_phase_e2e_opset17.onnx"
    partition_path = destination / "time_power_phase_npu_partition_opset17.onnx"
    torch.onnx.export(
        model,
        iq,
        end_to_end_path,
        opset_version=17,
        input_names=["iq"],
        output_names=["logits"],
        dynamo=False,
    )
    torch.onnx.export(
        partition,
        (iq, physical),
        partition_path,
        opset_version=17,
        input_names=["iq", "physical_features"],
        output_names=["logits"],
        dynamo=False,
    )

    report: dict[str, Any] = {
        "scope": "Frozen TimePowerPhase best checkpoint only; final_blind_test was not accessed.",
        "checkpoint": {
            "path": str(checkpoint),
            "sha256": _sha256(checkpoint),
            "epoch": int(checkpoint_data["epoch"]),
            "best_epoch": int(checkpoint_data["best_epoch"]),
        },
        "class_order": classes,
        "logical_contract": {
            "iq": [1, 2, sample_length],
            "physical_features": [1, 3, sample_length],
            "physical_channel_order": ["power", "lag1_real", "lag1_imag"],
            "logits": [1, len(classes)],
            "dtype": "float32 reference; planned calibrated symmetric INT8 NPU tensors",
        },
        "torch_partition_max_abs_error": parity_error,
        "end_to_end": _inspect(end_to_end_path),
        "npu_partition": _inspect(partition_path),
        "runtime_numerical_check": "TODO-NPU: onnxruntime is not installed; run converter/runtime parity on the target toolchain.",
        "vendor_operator_check": "TODO-HARDWARE: validate every op with the exact Icraft/FMQL30TAI release supplied with the board.",
    }
    report_path = destination / "deployment_export_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v2.yaml")
    parser.add_argument(
        "--checkpoint",
        default="outputs/qam_aware_v2/formal/time_power_phase/checkpoints/best.pt",
    )
    parser.add_argument("--output-dir", default="outputs/deployment_prep/time_power_phase")
    args = parser.parse_args()
    print(json.dumps(export_candidate(args.config, args.checkpoint, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
