#!/usr/bin/env python3
"""Compare one exact board NPU input across frozen PyTorch and board NPU.

This is a diagnostic, not an accuracy test.  It separates three contracts:
reference baseline generation, board preprocessing input bytes, and PyTorch/NPU
backend inference.  Labels are reported but never used in the verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


def die(msg: str) -> None:
    raise RuntimeError(msg)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_predictor(script_dir: Path):
    path = script_dir / "predict_clean_baseline.py"
    spec = importlib.util.spec_from_file_location("fix10prep1_clean_predictor", path)
    if spec is None or spec.loader is None:
        die("cannot load predictor module: %s" % path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_baseline(path: Path) -> dict[int, dict[str, str]]:
    want = ["source_index", "file_name", "sha256", "deployed_class",
            "split_role", "frozen_baseline_pred"]
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].split("\t") != want:
        die("bad clean baseline header")
    out: dict[int, dict[str, str]] = {}
    for lineno, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != len(want):
            die("baseline line %d: want 6 columns" % lineno)
        row = dict(zip(want, fields))
        key = int(row["source_index"])
        if key in out:
            die("duplicate baseline source_index=%d" % key)
        if row["split_role"] != "holdout":
            die("baseline source_index=%d is not holdout" % key)
        out[key] = row
    return out


def load_f32(path: Path, count: int) -> tuple[np.ndarray, str]:
    raw = path.read_bytes()
    if len(raw) != count * 4:
        die("%s size=%d, want=%d" % (path, len(raw), count * 4))
    arr = np.frombuffer(raw, dtype="<f4").copy()
    if not np.all(np.isfinite(arr)):
        die("%s contains non-finite values" % path)
    return arr, sha256_bytes(raw)


def infer(model, tensor: np.ndarray, torch, predictor) -> tuple[int, np.ndarray]:
    x = torch.from_numpy(tensor.reshape(2, 1024)).unsqueeze(0)
    with torch.inference_mode():
        logits, _ = model(x)
    raw = logits[0].detach().to(dtype=torch.float32, device="cpu").numpy()
    return predictor.merge_argmax(raw), raw


def top2(values: np.ndarray) -> tuple[int, int, float]:
    order = np.argsort(values, kind="stable")
    first, second = int(order[-1]), int(order[-2])
    return first, second, float(values[first] - values[second])


def classify_verdict(backend_bad: int, merge_bad: int, input_bad: int) -> str:
    if backend_bad:
        return "PYTORCH_NPU_BACKEND_DIVERGENCE"
    if merge_bad:
        return "BASELINE_MERGE_CONTRACT_ERROR"
    if input_bad:
        return "BASELINE_INPUT_DOMAIN_MISMATCH"
    return "FULL_DEPLOYMENT_AGREEMENT"


def self_test() -> int:
    cases = [
        ((1, 0, 0), "PYTORCH_NPU_BACKEND_DIVERGENCE"),
        ((0, 1, 0), "BASELINE_MERGE_CONTRACT_ERROR"),
        ((0, 0, 1), "BASELINE_INPUT_DOMAIN_MISMATCH"),
        ((0, 0, 0), "FULL_DEPLOYMENT_AGREEMENT"),
    ]
    passed = sum(classify_verdict(*args) == want for args, want in cases)
    print("analyze-clean self-test: %d/%d" % (passed, len(cases)))
    return 0 if passed == len(cases) else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--rml24-root")
    ap.add_argument("--config", default="configs/rml24_base.yaml")
    ap.add_argument("--checkpoint")
    ap.add_argument("--board-tensor-dir")
    ap.add_argument("--npu-logit-dir")
    ap.add_argument("--baseline")
    ap.add_argument("--manifest")
    ap.add_argument("--out")
    ap.add_argument("--expect-holdout", type=int, default=24)
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    for name in ("rml24_root", "checkpoint", "board_tensor_dir", "npu_logit_dir",
                 "baseline", "manifest", "out"):
        if getattr(args, name) is None:
            ap.error("--%s is required" % name.replace("_", "-"))

    predictor = load_predictor(Path(__file__).resolve().parent)
    manifest = predictor.parse_d2_manifest(Path(args.manifest))
    rows = [r for r in manifest if r["split_role"] == "holdout"]
    if len(rows) != args.expect_holdout:
        die("holdout=%d, want=%d" % (len(rows), args.expect_holdout))
    baseline = load_baseline(Path(args.baseline))
    if len(baseline) != args.expect_holdout:
        die("baseline rows=%d, want=%d" % (len(baseline), args.expect_holdout))

    rml24_root = Path(args.rml24_root).resolve()
    sys.path.insert(0, str(rml24_root))
    import torch
    from contracts.rml24_contract import LABEL_ORDER_24
    from models.rml24_net import build_rml24_model
    from training.utils import load_yaml

    ckpt = torch.load(Path(args.checkpoint), map_location="cpu", weights_only=False)
    if ckpt.get("class_names") not in (None, LABEL_ORDER_24) and \
            list(ckpt.get("class_names", [])) != list(LABEL_ORDER_24):
        die("checkpoint class_names mismatch")
    model = build_rml24_model(24, **load_yaml(rml24_root / args.config)["model"])
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.eval()

    board_dir = Path(args.board_tensor_dir)
    logits_dir = Path(args.npu_logit_dir)
    artifact_dir = Path(args.manifest).resolve().parent
    results = []
    backend_bad = 0
    input_bad = 0
    merge_bad = 0

    for row in rows:
        src = int(row["source_index"])
        if src not in baseline:
            die("missing baseline source_index=%d" % src)
        b = baseline[src]
        if b["file_name"] != row["quantized_file"] or \
                b["sha256"] != row["quantized_sha256"]:
            die("baseline identity mismatch source_index=%d" % src)
        stem = Path(row["quantized_file"]).stem
        board_tensor, board_sha = load_f32(
            board_dir / (stem + "__board_npu_input.f32"), 2048)
        npu_logits, npu_sha = load_f32(
            logits_dir / (stem + "__npu_logits.f32"), 24)
        ref_tensor, ref_sha = load_f32(
            artifact_dir / row["recovered_tensor_file"], 2048)
        if ref_sha != row["recovered_tensor_sha256"]:
            die("reference SHA mismatch source_index=%d" % src)

        torch_board_pred, torch_board_logits = infer(
            model, board_tensor, torch, predictor)
        torch_ref_pred, torch_ref_logits = infer(model, ref_tensor, torch, predictor)
        npu_pred = predictor.merge_argmax(npu_logits)
        old_ref_pred = predictor.SOURCE_TO_DEPLOYED[int(np.argmax(torch_ref_logits))]
        base_pred = int(b["frozen_baseline_pred"])

        board_merged = predictor.merge_logits_23(torch_board_logits)
        npu_merged = predictor.merge_logits_23(npu_logits)
        pt1, pt2, pm = top2(board_merged)
        nt1, nt2, nm = top2(npu_merged)
        tensor_delta = board_tensor.astype(np.float64) - ref_tensor
        board_vs_ref = torch_board_pred == torch_ref_pred
        backend_ok = torch_board_pred == npu_pred
        original_ok = torch_board_pred == base_pred
        merge_contract_error = base_pred == old_ref_pred and base_pred != torch_ref_pred
        backend_bad += int(not backend_ok)
        input_bad += int(not original_ok)
        merge_bad += int(merge_contract_error)
        results.append({
            "source_index": src,
            "file_name": row["quantized_file"],
            "source_label": int(row["raw24_class"]),
            "deployed_label": int(row["deployed23_class"]),
            "original_baseline_pred": base_pred,
            "pytorch_reference_tensor_pred": torch_ref_pred,
            "old_raw_argmax_mapping_pred": old_ref_pred,
            "pytorch_board_tensor_pred": torch_board_pred,
            "npu_board_tensor_pred": npu_pred,
            "pytorch_board_top1": pt1, "pytorch_board_top2": pt2,
            "pytorch_board_margin": pm,
            "npu_top1": nt1, "npu_top2": nt2, "npu_margin": nm,
            "reference_tensor_sha256": ref_sha,
            "board_tensor_sha256": board_sha,
            "npu_logits_sha256": npu_sha,
            "tensor_sha_equal": board_sha == ref_sha,
            "tensor_max_abs_error": float(np.max(np.abs(tensor_delta))),
            "tensor_rms_error": float(np.sqrt(np.mean(tensor_delta ** 2))),
            "pytorch_board_vs_reference": board_vs_ref,
            "pytorch_vs_original_baseline": original_ok,
            "npu_vs_pytorch": backend_ok,
            "merge_contract_error": merge_contract_error,
        })

    verdict = classify_verdict(backend_bad, merge_bad, input_bad)

    summary = {
        "verdict": verdict,
        "holdout": len(rows),
        "clean_input_domain_agreement": sum(
            int(r["pytorch_board_vs_reference"]) for r in results),
        "clean_backend_agreement": len(rows) - backend_bad,
        "clean_original_baseline_agreement": len(rows) - input_bad,
        "merge_contract_error_count": merge_bad,
        "results": results,
    }
    Path(args.out).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                              encoding="utf-8")
    print("CLEAN_INPUT_DOMAIN_AGREEMENT=%d/%d" %
          (summary["clean_input_domain_agreement"], len(rows)))
    print("CLEAN_BACKEND_AGREEMENT=%d/%d" %
          (summary["clean_backend_agreement"], len(rows)))
    print("CLEAN_ORIGINAL_BASELINE_AGREEMENT=%d/%d" %
          (summary["clean_original_baseline_agreement"], len(rows)))
    print("CLEAN_FIX10PREP1_VERDICT=%s" % verdict)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:
        print("CLEAN_FIX10PREP1_ERROR: %s" % exc, file=sys.stderr)
        sys.exit(1)
