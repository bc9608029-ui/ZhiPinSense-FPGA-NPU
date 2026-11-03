"""Export AD-AMR V1 (classification head) to ONNX and audit the NPU operator gap.

This is an *audit*, not a fit-to-whitelist gate.  AD-AMR is a research line; its
WaveUNet denoiser (ECA sigmoid, soft-threshold sign/abs, nearest upsample) is
expected to fall outside the frozen 8-operator NPU policy.  The exporter:

  * runs ``onnx.checker`` and asserts default-domain opset == 17;
  * lists every operator in the graph;
  * computes the gap vs the frozen NPU whitelist;
  * verifies ORT parity (onnxruntime vs torch, FP32);
  * writes ``export_report.json`` and ``deployment_gap_report.md``.

It never claims the graph is NPU-deployable.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import onnx
import torch
from onnx import TensorProto

from models.ad_amr_net import ADAMRClassifier, build_ad_amr_model, profile_ad_amr_model
from training.utils import ensure_output_dirs, load_yaml, select_device, set_seed

ALLOWED_OPS = {
    "Add", "BatchNormalization", "Concat", "Conv", "Gemm", "Mul", "ReduceMean", "Relu",
}
OPSET_VERSION = 17
FLOAT = TensorProto.DataType.Name(TensorProto.FLOAT)


def _default_opset(model: onnx.ModelProto) -> int:
    for imp in model.opset_import:
        if imp.domain in ("", "ai.onnx"):
            return int(imp.version)
    raise SystemExit("[ONNX audit] no default-domain opset import found")


def _inspect(path: Path) -> dict[str, object]:
    model = onnx.load(str(path))
    onnx.checker.check_model(model)
    opset = _default_opset(model)
    if opset != OPSET_VERSION:
        raise SystemExit(f"[ONNX audit] {path.name} default-domain opset {opset} != {OPSET_VERSION}")
    operators = Counter(node.op_type for node in model.graph.node)
    return {
        "checker_passed": True,
        "opset": opset,
        "op_types": dict(sorted(operators.items())),
        "file_size_bytes": path.stat().st_size,
    }


def _ort_parity(path: Path, model: torch.nn.Module, sample: torch.Tensor) -> dict[str, object]:
    try:
        import onnxruntime as ort
    except ImportError:
        return {"status": "skipped", "reason": "onnxruntime not installed"}

    with torch.inference_mode():
        torch_logits, _ = model(sample)
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    ort_logits = session.run(None, {"iq": sample.numpy()})[0]
    torch_np = torch_logits.cpu().numpy()
    max_abs = float((torch.from_numpy(ort_logits) - torch.from_numpy(torch_np)).abs().max().item())
    rel = float((torch.from_numpy(ort_logits) - torch.from_numpy(torch_np)).abs().mean().item())
    return {
        "status": "ok" if max_abs < 1e-3 else "mismatch",
        "max_abs_diff": max_abs,
        "mean_abs_diff": rel,
    }


def export_ad_amr(config_path: str, checkpoint_path: str | None = None) -> dict[str, object]:
    config = load_yaml(config_path)
    set_seed(int(config["seed"]))
    paths = ensure_output_dirs(config["output_root"])
    classes = [str(n).upper() for n in config["signal"]["modulations"]]
    sample_length = int(config["signal"]["sample_length"])

    checkpoint_file = Path(checkpoint_path) if checkpoint_path else paths["checkpoints"] / "best.pt"
    checkpoint = torch.load(checkpoint_file, map_location="cpu", weights_only=False)
    model = build_ad_amr_model(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"])
    model.eval()

    destination = paths["checkpoints"].parent / "onnx"
    destination.mkdir(parents=True, exist_ok=True)
    onnx_path = destination / "ad_amr_v1_classifier_opset17.onnx"
    sample = torch.zeros(1, 2, sample_length, dtype=torch.float32)

    torch.onnx.export(
        ADAMRClassifier(model).eval(),
        sample,
        str(onnx_path),
        opset_version=OPSET_VERSION,
        input_names=["iq"],
        output_names=["logits"],
        dynamo=False,
    )

    inspection = _inspect(onnx_path)
    actual = set(inspection["op_types"])
    gap = sorted(actual - ALLOWED_OPS)
    parity = _ort_parity(onnx_path, model, sample)
    profile = profile_ad_amr_model(model, sample_length)

    report = {
        "checkpoint": str(checkpoint_file),
        "checkpoint_epoch": int(checkpoint.get("epoch", -1)),
        "loss_variant": checkpoint.get("loss_variant"),
        "onnx_path": str(onnx_path),
        "inspection": inspection,
        "allowed_operator_policy": sorted(ALLOWED_OPS),
        "npu_whitelist_gap": gap,
        "npu_whitelist_gap_is_expected": True,
        "ort_parity": parity,
        "profile": profile,
        "note": "AD-AMR uses ops outside the frozen 8-op NPU policy; deployment is NOT claimed.",
    }
    (destination / "export_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Human-readable gap report.
    gap_lines = [
        "# AD-AMR V1 — Deployment Gap Report",
        "",
        "The AD-AMR Net (ICC 2024) is an independent research line.  Its denoising",
        "front-end (WaveUNet + ECA + adaptive soft-thresholding) was designed for",
        "classification accuracy, not for the frozen 8-operator NPU policy of the",
        "V2/V3.3 track.  This report documents that gap honestly.",
        "",
        "## Exported graph",
        f"- ONNX opset: {inspection['opset']}",
        f"- checker: {'passed' if inspection['checker_passed'] else 'FAILED'}",
        f"- operators: {json.dumps(inspection['op_types'])}",
        f"- parameter count: {profile['parameters']}",
        f"- neural MACs: {profile['neural_macs']}",
        "",
        "## Gap vs frozen NPU whitelist",
        f"Whitelist: {json.dumps(sorted(ALLOWED_OPS))}",
        f"Operators outside the whitelist: {json.dumps(gap)}",
        "",
    ]
    for op in gap:
        reasons = {
            "Sigmoid": "ECA channel-attention gating (GAP -> Conv1d -> Sigmoid -> multiply).",
            "Abs": "adaptive soft-thresholding |x| and the per-channel threshold magnitude.",
            "Sign": "soft-thresholding sign(x) * relu(|x| - lambda).",
            "Resize": "WaveUNet nearest-neighbour x2 upsampling in the ADM decoder.",
            "Upsample": "WaveUNet decoder upsampling (if traced as Upsample).",
            "Flatten": "vectorization before the FCL classifier.",
            "Dropout": "training-only; identity at export time (should not appear).",
            "Identity": "residual shortcut (may be folded by the exporter).",
        }
        gap_lines.append(f"- `{op}`: {reasons.get(op, 'see the traced graph.')}")
    gap_lines += [
        "",
        "## Conclusion",
        "Deployment to the ZG330 NPU under the current 8-op policy is NOT possible",
        "without re-architecting the denoiser (e.g. replacing soft-thresholding with",
        "a policy-approved op and nearest upsample with a transposed-conv variant,",
        "then re-validating).  No NPU deployment is claimed for AD-AMR V1.",
        "",
    ]
    (destination / "deployment_gap_report.md").write_text("\n".join(gap_lines), encoding="utf-8")

    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1.yaml")
    parser.add_argument("--checkpoint", default=None)
    args = parser.parse_args()
    report = export_ad_amr(args.config, args.checkpoint)
    print(json.dumps({
        "opset": report["inspection"]["opset"],
        "op_types": report["inspection"]["op_types"],
        "npu_whitelist_gap": report["npu_whitelist_gap"],
        "ort_parity": report["ort_parity"],
        "params": report["profile"]["parameters"],
    }, indent=2))


if __name__ == "__main__":
    main()
