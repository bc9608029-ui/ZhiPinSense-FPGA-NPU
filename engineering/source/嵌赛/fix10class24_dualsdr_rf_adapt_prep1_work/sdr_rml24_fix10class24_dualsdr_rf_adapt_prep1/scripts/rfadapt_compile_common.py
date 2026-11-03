#!/usr/bin/env python3
"""rfadapt_compile_common.py -- shared fail-closed gates for the compile scripts.

The rf-adapt BF16/TF32 compile is **conditional**: it runs ONLY if the FP32
candidate beats the original model on the independent test split (the go/no-go
decision recorded by the evaluator).  This module enforces that gate and
documents the iCraft compile procedure; it never fabricates a compiled model.

The iCraft compile itself (quantize -> adapt -> generate, network `model_24class`,
ai_target `@zhuget(330)`, qdtype bf16|tf32) is performed with the iCraft SDK in
the icraft environment; this scaffold refuses to emit a model unless a
``--sdk-compile`` hook is supplied and returns exit 0.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, os.pardir, "contracts"))
import rml24_dualsdr_rf_dataset_v1 as C  # noqa: E402


def _fail(msg, code=2):
    print(msg, file=sys.stderr)
    return code


def check_go_gate(go_json_path):
    """Return (candidate_acc, baseline_acc) if go; otherwise SystemExit."""
    if not go_json_path or not os.path.isfile(go_json_path):
        raise SystemExit(_fail(
            f"go/no-go JSON not found: {go_json_path} -- compile is gated on "
            f"'FP32 candidate beats original on independent test'; refusing to compile"))
    data = json.loads(Path(go_json_path).read_text(encoding="utf-8"))
    if not isinstance(data.get("go"), bool) or data["go"] is not True:
        raise SystemExit(_fail(
            f"go gate is not True in {go_json_path} (go={data.get('go')!r}); "
            f"refusing to compile a non-winning candidate"))
    cand = data.get("candidate_test_accuracy")
    base = data.get("baseline_test_accuracy")
    if not (isinstance(cand, (int, float)) and isinstance(base, (int, float))):
        raise SystemExit(_fail(f"{go_json_path}: missing accuracy fields"))
    if not cand > base:
        raise SystemExit(_fail(
            f"candidate {cand} does not beat baseline {base}; refusing to compile"))
    return cand, base


def require_onnx(onnx_path):
    if not onnx_path or not os.path.isfile(onnx_path):
        raise SystemExit(_fail(
            f"ONNX not found: {onnx_path} -- run export_fix10class24_rf_adapt_onnx.py first"))
    return C.sha256_file(onnx_path)


def manual_procedure(qdtype, onnx_path, out_dir):
    return (
        f"MANUAL iCRAFT COMPILE (no --sdk-compile hook supplied):\n"
        f"  1. iCraft SDK 3.39.0: import {onnx_path}, network name `{C.NETWORK_NAME}`.\n"
        f"  2. quantize: qdtype={qdtype}, full network, ai_target @zhuget(330).\n"
        f"  3. adapt: no int8 (full {qdtype}, no silent fallback).\n"
        f"  4. generate: emit .json + .raw.\n"
        f"  5. copy to {out_dir}/rml24_rfadapt_{qdtype}.{{json,raw}} and write "
        f"SHA256SUMS.txt + compiler_metadata.json (source checkpoint + label contract).\n"
        f"  Then re-run with --sdk-compile <hook> to automate, or record the "
        f"produced SHA256SUMS in the audit doc."
    )


def compile_main(qdtype):
    ap = argparse.ArgumentParser(
        description=f"compile the rf-adapt FP32 candidate to iCraft {qdtype.upper()} "
                    f"(gated on go/no-go).",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go-from", required=True,
                    help="go/no-go JSON from the evaluator (go=true, candidate>baseline)")
    ap.add_argument("--onnx", default="model_rml24_rfadapt_fp32/rml24_rfadapt_opset17.onnx")
    ap.add_argument("--output", default=f"model_rml24_rfadapt_{qdtype}")
    ap.add_argument("--sdk-compile", default=None,
                    help="optional iCraft SDK compile hook (must exit 0 on success)")
    args = ap.parse_args()

    cand, base = check_go_gate(args.go_from)
    onnx_sha = require_onnx(args.onnx)
    out_dir = Path(args.output)

    print(f"go gate PASS: candidate {cand} > baseline {base}")
    print(f"onnx {args.onnx} sha256={onnx_sha}")
    print(f"qdtype={qdtype} target={out_dir} (new dir; never overwrites production)")

    if not args.sdk_compile:
        raise SystemExit(_fail(manual_procedure(qdtype, args.onnx, str(out_dir))))
    if not os.path.isfile(args.sdk_compile):
        raise SystemExit(_fail(f"--sdk-compile hook not found: {args.sdk_compile}"))

    import subprocess
    out_dir.mkdir(parents=True, exist_ok=True)
    rc = subprocess.call([
        sys.executable, args.sdk_compile, "--onnx", args.onnx,
        "--qdtype", qdtype, "--output", str(out_dir),
        "--network", C.NETWORK_NAME,
    ])
    if rc != 0:
        raise SystemExit(_fail(f"iCraft compile hook exited {rc}; no model emitted"))
    print(f"compile hook exit 0 -> {out_dir}")
    return 0
