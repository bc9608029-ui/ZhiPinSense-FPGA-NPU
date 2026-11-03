"""Export and strictly gate the deployable 24-class ONNX graph.

Mirrors ``scripts.export_ad_amr_v1_1_onnx`` but pins the frozen 24-class contract
(``RML24Classifier``, ``num_classes=24``, raw logits) and a 24-class-specific
output filename.  The operator whitelist, opset, and ONNX Runtime parity gates
are identical to the 12-class exporter.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import torch

from contracts.rml24_contract import LABEL_ORDER_24
from models.ad_amr_v1_1_net import profile_ad_amr_v1_1
from models.rml24_net import RML24Classifier, build_rml24_model
from scripts.export_ad_amr_v1_1_onnx import OPSET_VERSION, _ort_parity, inspect_onnx
from training.utils import ensure_output_dirs, load_yaml, save_json


def export_rml24(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path) -> dict[str, Any]:
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    classes = list(LABEL_ORDER_24)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if list(checkpoint.get("class_names", [])) != classes:
        raise RuntimeError("24-class checkpoint class order differs from the frozen contract")
    model = build_rml24_model(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    wrapper = RML24Classifier(model).eval()
    root = ensure_output_dirs(config["output_root"])["checkpoints"].parent
    output = root / "onnx"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "rml24_opset17.onnx"
    sample_length = int(config.get("signal", {}).get("sample_length", 1024))
    sample = torch.zeros(1, 2, sample_length, dtype=torch.float32)
    torch.onnx.export(wrapper, sample, str(path), opset_version=OPSET_VERSION,
                      input_names=["iq"], output_names=["logits"], dynamo=False)
    inspection = inspect_onnx(path)
    if inspection["opset"] != OPSET_VERSION:
        raise RuntimeError(f"ONNX opset {inspection['opset']} != {OPSET_VERSION}")
    if inspection["unexpected_operators"]:
        raise RuntimeError(f"NPU operator gate failed: {inspection['unexpected_operators']}")
    parity = _ort_parity(path, wrapper, sample)
    if parity["status"] != "ok":
        raise RuntimeError(f"ONNX Runtime parity failed: {parity}")
    report = {
        "onnx_path": str(path), "checkpoint": str(checkpoint_path),
        "checkpoint_epoch": int(checkpoint["epoch"]), "inspection": inspection,
        "ort_parity": parity, "profile": profile_ad_amr_v1_1(model, sample_length),
        "npu_graph_claim": "operator-compatible only; vendor compilation and board parity remain required",
    }
    save_json(report, output / "export_report.json")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()
    print(json.dumps(export_rml24(args.config, args.checkpoint), indent=2))


if __name__ == "__main__":
    main()
