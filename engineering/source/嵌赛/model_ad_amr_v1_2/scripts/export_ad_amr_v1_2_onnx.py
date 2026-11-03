"""Export the unchanged V1.1 student graph as the V1.2 data candidate."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import torch

from models.ad_amr_v1_1_net import ADAMRV11Classifier, build_ad_amr_v1_1_model, profile_ad_amr_v1_1
from scripts.export_ad_amr_v1_1_onnx import OPSET_VERSION, _ort_parity, inspect_onnx
from training.utils import ensure_output_dirs, load_yaml, save_json


def export_v1_2(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path) -> dict[str, Any]:
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    classes = [str(value).upper() for value in config["signal"]["modulations"]]
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if checkpoint.get("track") != "ad_amr_v1_2":
        raise RuntimeError("V1.2 export requires a V1.2 checkpoint")
    model = build_ad_amr_v1_1_model(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    wrapper = ADAMRV11Classifier(model).eval()
    root = ensure_output_dirs(config["output_root"])["checkpoints"].parent
    output = root / "onnx"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "ad_amr_v1_2_opset17.onnx"
    sample = torch.zeros(1, 2, int(config["signal"]["sample_length"]), dtype=torch.float32)
    torch.onnx.export(wrapper, sample, str(path), opset_version=OPSET_VERSION,
                      input_names=["iq"], output_names=["logits"], dynamo=False)
    inspection = inspect_onnx(path)
    if inspection["opset"] != OPSET_VERSION or inspection["unexpected_operators"]:
        raise RuntimeError(f"V1.2 NPU operator gate failed: {inspection}")
    parity = _ort_parity(path, wrapper, sample)
    if parity["status"] != "ok":
        raise RuntimeError(f"V1.2 ONNX Runtime parity failed: {parity}")
    report = {
        "track": "ad_amr_v1_2", "onnx_path": str(path), "checkpoint": str(checkpoint_path),
        "checkpoint_epoch": int(checkpoint["epoch"]), "inspection": inspection,
        "ort_parity": parity, "profile": profile_ad_amr_v1_1(model, sample.shape[-1]),
        "npu_graph_claim": "operator-compatible only; vendor compilation and board parity remain required",
    }
    save_json(report, output / "export_report.json")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1_2.yaml")
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()
    print(json.dumps(export_v1_2(args.config, args.checkpoint), indent=2))


if __name__ == "__main__":
    main()
