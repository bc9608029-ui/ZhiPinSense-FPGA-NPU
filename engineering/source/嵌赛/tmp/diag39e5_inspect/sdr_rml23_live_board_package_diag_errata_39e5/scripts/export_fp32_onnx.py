#!/usr/bin/env python3
"""export_fp32_onnx.py -- FP32 backend raw-24 logits export (errata 39e5 Stage E).

Runs the FP32 source model (work/onnx/rml24_24class_opset17.onnx) via
onnxruntime on the exact [2,1024] fp32 tensors that the board also classifies,
and writes one JSON record per frame in the SAME schema as the board-NPU export
(board_package/logits_export.hpp):

    {"backend": "fp32_onnx", "frame_id": N, "input_sha256": "<64 hex>",
     "model_sha": "<onnx file sha256>",
     "compiled_model_raw_sha256": "2425d990...",
     "raw24": [24 float pre-merge logits]}

Keyed by the input's SHA-256 so scripts/compare_three_backends.py only ever
compares logits produced from IDENTICAL input bytes.  The ONNX output is `logits`
[1,24] (raw, pre-softmax, pre-merge) -- the last op is a Gemm, no softmax -- so it
is directly comparable to the Host/board raw-24 logits after the same 24->23
merge.

This is one of the three backends; it does NOT claim any verdict by itself.

Usage:
    python scripts/export_fp32_onnx.py --input-dir deployment_golden \
        --onnx ../work/onnx/rml24_24class_opset17.onnx --out-dir /tmp/fp32

If onnxruntime is not installed, the script exits non-zero with the pending
command (``pip install onnxruntime``) -- it never fabricates logits.
"""

import argparse
import glob
import hashlib
import json
import os
import sys

import numpy as np

FROZEN_MODEL_RAW_SHA256 = "2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba"


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def load_tensor(path):
    raw = open(path, "rb").read()
    if len(raw) != 8192:
        raise ValueError("%s is %d bytes, want 8192" % (path, len(raw)))
    iq = np.frombuffer(raw, dtype="<f4").reshape(2, 1024).astype(np.float32)
    return raw, iq


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input-dir", default="deployment_golden",
                    help="dir of input_NNN.bin or live_rx_tensor_NNN.f32")
    ap.add_argument("--onnx", default=None,
                    help="path to rml24_24class_opset17.onnx")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    try:
        import onnxruntime as ort  # noqa: F401
    except ImportError:
        print("FP32 backend UNAVAILABLE: onnxruntime not installed.\n"
              "  pending command: pip install onnxruntime", file=sys.stderr)
        return 2

    onnx_path = args.onnx
    if not onnx_path:
        # default: sibling repo layout work/onnx/rml24_24class_opset17.onnx
        here = os.path.dirname(os.path.abspath(__file__))
        onnx_path = os.path.join(here, os.pardir, os.pardir,
                                 "work", "onnx", "rml24_24class_opset17.onnx")
    onnx_path = os.path.abspath(onnx_path)
    if not os.path.isfile(onnx_path):
        print("FP32 backend UNAVAILABLE: ONNX not found at %s" % onnx_path,
              file=sys.stderr)
        return 2

    onnx_sha = sha256_bytes(open(onnx_path, "rb").read())

    pats = ["input_*.bin", "live_rx_tensor_*.f32"]
    paths = []
    for p in pats:
        paths.extend(glob.glob(os.path.join(args.input_dir, p)))
    paths = sorted(paths)
    if not paths:
        print("no input_*.bin / live_rx_tensor_*.f32 under %s" % args.input_dir,
              file=sys.stderr)
        return 1

    import onnxruntime as ort
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    os.makedirs(args.out_dir, exist_ok=True)

    n = 0
    for path in paths:
        name = os.path.basename(path)
        if name.startswith("input_"):
            fid = int(name[len("input_"):-len(".bin")])
        else:
            fid = int(name[len("live_rx_tensor_"):-len(".f32")])
        raw, iq = load_tensor(path)
        inp_sha = sha256_bytes(raw)
        out = sess.run(None, {in_name: iq[np.newaxis, :, :]})[0]
        raw24 = [float(v) for v in out[0]]
        rec = {
            "backend": "fp32_onnx",
            "frame_id": fid,
            "input_sha256": inp_sha,
            "model_sha": onnx_sha,
            "compiled_model_raw_sha256": FROZEN_MODEL_RAW_SHA256,
            "raw24": raw24,
        }
        out_path = os.path.join(args.out_dir, "logits_%d.json" % fid)
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rec, f)
        os.replace(tmp, out_path)
        n += 1

    print("export_fp32_onnx: %d frames -> %s" % (n, args.out_dir))
    print("  onnx=%s sha256=%s" % (onnx_path, onnx_sha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
