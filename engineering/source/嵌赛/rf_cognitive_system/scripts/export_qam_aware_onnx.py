"""Export QAM-Aware V2 models to ONNX opset 17 and inspect operators."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import onnx
import torch

from models.qam_aware_rfnet import build_qam_aware_model, qam_aware_model_profile
from training.qam_aware_utils import load_qam_aware_config
from training.utils import resolve_project_path


def export_models(config_path: str) -> dict[str, object]:
    config = load_qam_aware_config(config_path)
    root = resolve_project_path("outputs/qam_aware_v2")
    destination = root / "onnx"
    destination.mkdir(parents=True, exist_ok=True)
    classes = list(config["signal"]["modulations"])
    sample_length = int(config["signal"]["sample_length"])
    report: dict[str, object] = {}
    for variant in config["variants"]:
        model = build_qam_aware_model(variant, len(classes), **config["qam_aware"]).eval()
        output = destination / f"{variant}.onnx"
        torch.onnx.export(
            model,
            torch.zeros(1, 2, sample_length, dtype=torch.float32),
            output,
            opset_version=17,
            input_names=["iq"],
            output_names=["logits"],
            dynamo=False,
        )
        graph = onnx.load(output)
        onnx.checker.check_model(graph)
        operator_counts = Counter(node.op_type for node in graph.graph.node)
        profile = qam_aware_model_profile(model, sample_length)
        report[variant] = {
            "checker_passed": True,
            "opset": max(item.version for item in graph.opset_import),
            "op_types": dict(sorted(operator_counts.items())),
            "onnx_file_size_mb": output.stat().st_size / (1024**2),
            "profile": profile,
        }
    (destination / "export_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v2.yaml")
    args = parser.parse_args()
    print(json.dumps(export_models(args.config), indent=2))


if __name__ == "__main__":
    main()
