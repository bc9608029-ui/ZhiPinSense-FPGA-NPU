"""Export V3.1 training and FPGA-partitioned graphs to ONNX opset 17."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import onnx
import torch

from models.qam_aware_rfnet_v3_1 import build_qam_aware_v3_1, build_qam_aware_v3_1_partition
from training.qam_aware_v3_1_utils import load_qam_aware_v3_1_config
from training.utils import ensure_output_dirs


def _inspect(path: Path) -> dict[str, object]:
    graph = onnx.load(path)
    onnx.checker.check_model(graph)
    operators = Counter(node.op_type for node in graph.graph.node)
    return {
        "checker_passed": True,
        "opset": max(item.version for item in graph.opset_import),
        "op_types": dict(sorted(operators.items())),
        "file_size_bytes": path.stat().st_size,
    }


def export_v3_1(config_path: str, checkpoint_path: str | None = None) -> dict[str, object]:
    config = load_qam_aware_v3_1_config(config_path)
    paths = ensure_output_dirs(config["output_root"])
    checkpoint_file = Path(checkpoint_path) if checkpoint_path else paths["checkpoints"] / "best.pt"
    checkpoint = torch.load(checkpoint_file, map_location="cpu", weights_only=False)
    classes = list(config["signal"]["modulations"])
    length = int(config["signal"]["sample_length"])
    model = build_qam_aware_v3_1(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    destination = paths["checkpoints"].parent / "onnx"
    destination.mkdir(parents=True, exist_ok=True)
    e2e_path = destination / "qam_aware_v3_1_e2e_opset17.onnx"
    partition_path = destination / "qam_aware_v3_1_npu_partition_opset17.onnx"
    iq = torch.zeros(1, 2, length, dtype=torch.float32)
    physical = torch.zeros(1, 3, length, dtype=torch.float32)

    torch.onnx.export(
        model,
        iq,
        e2e_path,
        opset_version=17,
        input_names=["iq"],
        output_names=["logits"],
        dynamo=False,
    )
    torch.onnx.export(
        build_qam_aware_v3_1_partition(model).eval(),
        (iq, physical),
        partition_path,
        opset_version=17,
        input_names=["iq", "physical_features"],
        output_names=["logits"],
        dynamo=False,
    )
    allowed = {"Add", "BatchNormalization", "Concat", "Conv", "Gemm", "Mul", "ReduceMean", "Relu"}
    report = {
        "checkpoint": str(checkpoint_file),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "e2e": _inspect(e2e_path),
        "npu_partition": _inspect(partition_path),
        "allowed_operator_policy": sorted(allowed),
    }
    actual = set(report["npu_partition"]["op_types"])
    report["npu_partition"]["unexpected_operators"] = sorted(actual - allowed)
    (destination / "export_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_1_smoke.yaml")
    parser.add_argument("--checkpoint", default=None)
    args = parser.parse_args()
    print(json.dumps(export_v3_1(args.config, args.checkpoint), indent=2))


if __name__ == "__main__":
    main()
