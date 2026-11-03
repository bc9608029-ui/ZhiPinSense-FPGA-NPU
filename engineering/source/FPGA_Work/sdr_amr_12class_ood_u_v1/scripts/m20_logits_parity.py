"""M20 logits parity (Section 十一, question 5).

Two-way (PyTorch fp32 vs ONNX fp32) parity is verified fail-closed on the fixed
IQ parity set.  When an NPU-captured logits file is supplied, a three-way check
against the board output is added, using the documented int8 quantization
tolerance (the output is auto-dequantized to fp32 at the boundary).
"""

from __future__ import annotations

import argparse
from typing import Any

import numpy as np

from ood.scores import compute_scores
from ood_u.manifest import read_ood_u_manifest
from ood_u.model import load_model, predict_logits, predict_logits_onnx
from scripts.m20_common import (
    PROJECT_ROOT,
    add_common_args,
    emit_result,
    new_run_id,
    resolve_path,
    run,
    write_json,
)
from scripts.m20_parity_data import build_parity_iq
from tools.compare_logits import (
    FP32_MAX_ABS_DIFF,
    NPU_MAX_ABS_DIFF,
    compare_logits,
    read_logits_file,
)


def main(args: argparse.Namespace) -> None:
    run_id = new_run_id()
    out_dir = resolve_path(args.out_dir or "runs/m20_logits_parity")
    model = load_model(resolve_path(args.checkpoint))
    onnx_path = resolve_path("model_12class/ad_amr_v1_1_opset17.onnx")

    planar, labels = build_parity_iq()
    pt_logits = predict_logits(model, planar)
    onnx_logits = predict_logits_onnx(onnx_path, planar)

    comparisons: list[dict[str, Any]] = [
        {"reference": "pytorch_fp32", **compare_logits(pt_logits, onnx_logits, FP32_MAX_ABS_DIFF)},
    ]

    npu_logits = None
    if args.npu_logits:
        npu_logits = read_logits_file(resolve_path(args.npu_logits), "NPU")
        comparisons.append({"reference": "pytorch_fp32", **compare_logits(pt_logits, npu_logits, NPU_MAX_ABS_DIFF)})

    # OOD decision agreement at the frozen threshold (when a manifest is available).
    decision_agreement: dict[str, Any] | None = None
    if args.manifest:
        manifest = read_ood_u_manifest(resolve_path(args.manifest))
        method = manifest["score_method"]
        temperature = manifest["temperature"]
        threshold = manifest["threshold"]
        ref_score = compute_scores(pt_logits, method, temperature)
        onnx_score = compute_scores(onnx_logits, method, temperature)
        ref_decision = ref_score > threshold
        onnx_decision = onnx_score > threshold
        decision_agreement = {
            "score_method": method,
            "temperature": temperature,
            "threshold": threshold,
            "pytorch_vs_onnx_decision_agreement": float(np.mean(ref_decision == onnx_decision)),
        }
        if npu_logits is not None:
            npu_score = compute_scores(npu_logits, method, temperature)
            decision_agreement["pytorch_vs_npu_decision_agreement"] = float(
                np.mean(ref_decision == (npu_score > threshold)))

    all_ok = all(c["within_tolerance"] for c in comparisons)
    report: dict[str, Any] = {
        "run_id": run_id,
        "step": "logits_parity",
        "n_samples": len(planar),
        "labels": labels,
        "comparisons": comparisons,
        "decision_agreement": decision_agreement,
        "fp32_tolerance": FP32_MAX_ABS_DIFF,
        "npu_int8_tolerance": NPU_MAX_ABS_DIFF,
        "npu_logits_provided": npu_logits is not None,
    }
    out_path = write_json(out_dir / "logits_parity_report.json", report)
    if not all_ok:
        from scripts.m20_common import fail
        fail(run_id, f"parity tolerance exceeded: {[(c['reference'], c['max_abs_diff']) for c in comparisons if not c['within_tolerance']]}")

    emit_result("PASS", run_id,
                pytorch_vs_onnx_max_abs=comparisons[0]["max_abs_diff"],
                argmax_agreement=comparisons[0]["argmax_agreement"],
                npu_provided=npu_logits is not None,
                report=str(out_path.relative_to(PROJECT_ROOT)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M20 logits parity")
    add_common_args(parser)
    parser.add_argument("--npu-logits", default=None, help="NPU-captured logits JSON (optional)")
    parser.add_argument("--manifest", default=None, help="frozen OOD-U manifest (for decision agreement)")
    return parser


if __name__ == "__main__":
    run(build_parser(), main)
