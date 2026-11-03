"""Export and strictly gate the deployable V1.1 ONNX graph."""

from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

import onnx
import torch

from models.ad_amr_v1_1_net import ADAMRV11Classifier, build_ad_amr_v1_1_model, profile_ad_amr_v1_1
from training.utils import ensure_output_dirs, load_yaml, save_json

ALLOWED_OPS = {"Add", "BatchNormalization", "Conv", "Gemm", "ReduceMean", "Relu"}
OPSET_VERSION = 17


def inspect_onnx(path: str | Path) -> dict[str, Any]:
    model = onnx.load(str(path))
    onnx.checker.check_model(model)
    opset = next(int(value.version) for value in model.opset_import if value.domain in ("", "ai.onnx"))
    operators = Counter(node.op_type for node in model.graph.node)
    unexpected = sorted(set(operators) - ALLOWED_OPS)
    return {
        "checker_passed": True, "opset": opset,
        "op_types": dict(sorted(operators.items())), "unexpected_operators": unexpected,
    }


def _ort_parity(path: Path, wrapper: torch.nn.Module, sample: torch.Tensor) -> dict[str, Any]:
    import onnxruntime as ort
    with torch.inference_mode():
        expected = wrapper(sample).cpu()
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    actual = torch.from_numpy(session.run(None, {"iq": sample.numpy()})[0])
    difference = (actual - expected).abs()
    return {
        "status": "ok" if float(difference.max()) < 1e-3 else "mismatch",
        "max_abs_diff": float(difference.max()), "mean_abs_diff": float(difference.mean()),
    }


def export_v1_1(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path) -> dict[str, Any]:
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    classes = [str(v).upper() for v in config["signal"]["modulations"]]
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    model = build_ad_amr_v1_1_model(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    # Eval the wrapper itself, not only the child.  The legacy exporter restores
    # the top-level module's original training flag recursively after export.
    wrapper = ADAMRV11Classifier(model).eval()
    root = ensure_output_dirs(config["output_root"])["checkpoints"].parent
    output = root / "onnx"
    output.mkdir(parents=True, exist_ok=True)
    path = output / "ad_amr_v1_1_opset17.onnx"
    sample = torch.zeros(1, 2, int(config["signal"]["sample_length"]), dtype=torch.float32)
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
        "ort_parity": parity, "profile": profile_ad_amr_v1_1(model, sample.shape[-1]),
        "npu_graph_claim": "operator-compatible only; vendor compilation and board parity remain required",
    }
    save_json(report, output / "export_report.json")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1_1.yaml")
    parser.add_argument("--checkpoint", required=True)
    args = parser.parse_args()
    print(json.dumps(export_v1_1(args.config, args.checkpoint), indent=2))


if __name__ == "__main__":
    main()
