#!/usr/bin/env python3
"""export_fix10class24_rf_adapt_onnx.py -- export a fine-tuned checkpoint to ONNX.

Runs only in the training environment (torch required, fail-closed otherwise).
Exports the FP32 candidate checkpoint to ``model_rml24_rfadapt_fp32/`` as opset17,
network name ``model_24class``, I/O ``[1,2,1024]`` fp32 -> ``[1,24]`` fp32.

This is a NEW output directory; it never overwrites the production
``model_rml24_bf16/`` or the sibling ``model_rml24_tf32/``.

Usage::

    python scripts/export_fix10class24_rf_adapt_onnx.py \
        --checkpoint runs/pilot/best.pt --model-def <module> \
        --output model_rml24_rfadapt_fp32/rml24_rfadapt_opset17.onnx
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "contracts"))
import rml24_dualsdr_rf_dataset_v1 as C  # noqa: E402


def require_torch():
    try:
        import torch  # noqa: F401
        return torch
    except ImportError:
        raise SystemExit("torch not available; export runs in the training env")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--model-def", required=True,
                    help="path to module exposing build_model(num_classes=24)")
    ap.add_argument("--output", default="model_rml24_rfadapt_fp32/rml24_rfadapt_opset17.onnx")
    args = ap.parse_args()

    torch = require_torch()
    import importlib.util

    if not os.path.isfile(args.model_def):
        raise SystemExit(f"model-def not found: {args.model_def}")
    spec = importlib.util.spec_from_file_location("rf_adapt_model_def", args.model_def)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    build_model = getattr(mod, "build_model", None)
    if build_model is None:
        raise SystemExit(f"{args.model_def}: missing build_model(num_classes)")

    model = build_model(num_classes=C.SOURCE_CLASS_COUNT)
    ckpt = torch.load(args.checkpoint, map_location="cpu")
    state = ckpt.get("model_state_dict", ckpt.get("state_dict", ckpt))
    model.load_state_dict(state, strict=True)
    model.eval()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.zeros(1, 2, 1024, dtype=torch.float32)
    torch.onnx.export(
        model, dummy, str(out_path),
        input_names=["input"], output_names=["logits"],
        dynamic_axes=None, opset_version=17,
        do_constant_folding=True,
    )
    print(f"ONNX exported -> {out_path}")
    print(f"onnx_sha256 = {C.sha256_file(out_path)}")
    print("NOTE: verify network name/model identity at iCraft import time (model_24class).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
