#!/usr/bin/env python3
"""run_three_backend_judgment.py -- M29 RML23 real-external-QPSK three-backend
root-cause judgment (binding directive 39e5, 2026-10-11).

Runs, on the IDENTICAL 8192 input bytes of every live_rx_tensor_*.f32 capture,
three independent backends and adjudicates the QPSK->QAM misclassification:

    A. board_npu      -> read the saved raw24 logits (board_logits/logits_*.json)
    B. host_quantized -> iCraft HostBackend on the frozen compiled bf16 model
                         (icraft-run --backends Host), same bytes as the board
    C. fp32_onnx      -> the FP32 source model (work/onnx/rml24_24class_opset17.onnx)

Rules (binding directive):
    all three QAM                       -> model / real-domain generalization
    FP32=QPSK, Host/NPU=QAM             -> quantization / compile
    FP32/Host=QPSK, NPU=QAM             -> board NPU / runtime / input-buffer
    three-way unstable                  -> check model identity + backend input

This script NEVER re-normalizes, IQ-swaps, reorders, filters, resamples or edits
the tensor.  The 24->23 merge reuses the frozen postprocess/rml23_merged.py.

Pure stdlib + numpy + onnxruntime (fp32) + icraft-run.exe (host).  It writes its
own outputs under <out_dir> and prints a human-readable verdict to stdout.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np

# ---- frozen identities (binding) ------------------------------------------
FROZEN_MODEL_JSON_SHA = "d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d"
FROZEN_MODEL_RAW_SHA = "2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba"
FROZEN_PARAMS_MD5 = "7966a4829fc713b2e8ea6c04168be263"

LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)

# class indices the directive asks to report per frame
REPORT_CLASSES = {
    "BPSK": 3, "QPSK": 4, "16QAM": 12, "64QAM": 14, "128QAM": 15, "256QAM": 16,
}

# ---- merge (frozen reuse) --------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_POSTPROC = os.path.join(_HERE, os.pardir, os.pardir, "postprocess")
if not os.path.isdir(_POSTPROC):
    # fall back to the frozen project root (postprocess sits next to board_rml23_live)
    _POSTPROC = os.path.join(_HERE, os.pardir, os.pardir, "postprocess")
sys.path.insert(0, os.path.abspath(_POSTPROC))
from rml23_merged import merge_logits_24_to_23  # noqa: E402


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def softmax23(raw24):
    m = merge_logits_24_to_23([float(v) for v in raw24])
    m = np.asarray(m, dtype=np.float64)
    m = m - m.max()
    e = np.exp(m)
    p = e / e.sum()
    return p


def load_board_logits(board_dir):
    """{frame_id: {"raw24": [...], "model_sha": str, "input_sha256": str}}"""
    out = {}
    for path in sorted(glob.glob(os.path.join(board_dir, "logits_*.json"))):
        fid = int(os.path.basename(path)[len("logits_"):-len(".json")])
        r = json.load(open(path, encoding="utf-8"))
        if r.get("backend") != "board_npu":
            raise ValueError("%s backend != board_npu" % path)
        if r.get("model_sha") != FROZEN_MODEL_RAW_SHA:
            raise ValueError("board logits model_sha %r != frozen" % r.get("model_sha"))
        out[fid] = r
    return out


def run_fp32(onnx_path, tensor_paths, out_dir):
    import onnxruntime as ort
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    onnx_sha = sha256_file(onnx_path)
    os.makedirs(out_dir, exist_ok=True)
    out = {}
    for path in tensor_paths:
        fid = int(os.path.basename(path)[len("live_rx_tensor_"):-len(".f32")])
        raw = open(path, "rb").read()
        iq = np.frombuffer(raw, dtype="<f4").reshape(2, 1024).astype(np.float32)
        logits = sess.run(None, {in_name: iq[np.newaxis, :, :]})[0][0]
        raw24 = [float(v) for v in logits]
        out[fid] = {"raw24": raw24, "input_sha256": sha256_bytes(raw),
                    "model_sha": onnx_sha}
        rec = {"backend": "fp32_onnx", "frame_id": fid,
               "input_sha256": sha256_bytes(raw), "model_sha": onnx_sha,
               "compiled_model_raw_sha256": FROZEN_MODEL_RAW_SHA, "raw24": raw24}
        with open(os.path.join(out_dir, "logits_%d.json" % fid), "w", encoding="utf-8") as f:
            json.dump(rec, f)
    return out


def run_host(icraft_run, model_json, model_raw, tensor_paths, out_dir):
    """Run iCraft HostBackend on each tensor's identical bytes; ~1 sample/invocation."""
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, ".icraft_run")
    os.makedirs(work, exist_ok=True)
    ftmp_dir = os.path.join(work, ".icraft", "logs", "model_24class", "ftmpHQB")
    out = {}
    t0 = time.time()
    n = len(tensor_paths)
    for i, path in enumerate(sorted(tensor_paths)):
        fid = int(os.path.basename(path)[len("live_rx_tensor_"):-len(".f32")])
        raw = open(path, "rb").read()
        in_bin = os.path.join(work, "iq_%d.bin" % fid)
        with open(in_bin, "wb") as f:
            f.write(raw)
        for old in glob.glob(os.path.join(ftmp_dir, "*.ftmp")):
            os.remove(old)
        cmd = [icraft_run, "--json", model_json, "--raw", model_raw,
               "--network", "model_24class", "--input", in_bin,
               "--backends", "Host", "--dump_output"]
        subprocess.run(cmd, cwd=work, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True, timeout=180)
        ftmps = glob.glob(os.path.join(ftmp_dir, "*.ftmp"))
        if not ftmps:
            raise RuntimeError("no host ftmp output for frame %d" % fid)
        logits = np.fromfile(ftmps[0], dtype=np.float32)
        if logits.size != 24:
            raise RuntimeError("host output size %d for frame %d" % (logits.size, fid))
        raw24 = [float(v) for v in logits]
        out[fid] = {"raw24": raw24, "input_sha256": sha256_bytes(raw),
                    "model_sha": FROZEN_MODEL_RAW_SHA}
        rec = {"backend": "host_quantized", "frame_id": fid,
               "input_sha256": sha256_bytes(raw), "model_sha": FROZEN_MODEL_RAW_SHA,
               "raw24": raw24}
        with open(os.path.join(out_dir, "logits_%d.json" % fid), "w", encoding="utf-8") as f:
            json.dump(rec, f)
        if (i + 1) % 10 == 0 or (i + 1) == n:
            rate = (i + 1) / (time.time() - t0)
            print("  [host %d/%d] %.2f samp/s" % (i + 1, n, rate), file=sys.stderr)
    return out


def pair_stats(a, b):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    d = np.abs(a - b)
    cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-300))
    return float(d.max()), float(d.mean()), cos


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture-dir", required=True,
                    help="dir of live_rx_tensor_*.f32 files")
    ap.add_argument("--board-dir", required=True,
                    help="dir of board_npu logits_*.json")
    ap.add_argument("--onnx", required=True)
    ap.add_argument("--model-json", required=True)
    ap.add_argument("--model-raw", required=True)
    ap.add_argument("--icraft-run", default=r"D:\icraft\bin\icraft-run.exe")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--skip-host", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    # fail-closed identity
    mj = sha256_file(args.model_json)
    mr = sha256_file(args.model_raw)
    if mj != FROZEN_MODEL_JSON_SHA or mr != FROZEN_MODEL_RAW_SHA:
        sys.exit("model identity mismatch: json=%s raw=%s" % (mj, mr))
    with open(args.model_json, encoding="utf-8") as f:
        pmd5 = json.load(f).get("params_md5")
    print("model json SHA   = %s" % mj)
    print("model raw  SHA   = %s" % mr)
    print("params_md5       = %s  (frozen %s)" % (pmd5, FROZEN_PARAMS_MD5))

    tensors = sorted(glob.glob(os.path.join(args.capture_dir, "live_rx_tensor_*.f32")))
    if not tensors:
        sys.exit("no live_rx_tensor_*.f32 under %s" % args.capture_dir)

    board = load_board_logits(args.board_dir)
    print("board_npu frames = %d" % len(board))
    print("tensor files     = %d" % len(tensors))

    # tensor SHA map (frame -> sha of the exact bytes)
    tsha = {}
    for p in tensors:
        fid = int(os.path.basename(p)[len("live_rx_tensor_"):-len(".f32")])
        tsha[fid] = sha256_file(p)

    # A. board
    # (already loaded)

    # C. fp32
    fp32 = run_fp32(args.onnx, tensors, os.path.join(args.out_dir, "fp32_logits"))
    print("fp32_onnx frames = %d" % len(fp32))

    # B. host
    if not args.skip_host:
        host = run_host(args.icraft_run, args.model_json, args.model_raw,
                        tensors, os.path.join(args.out_dir, "host_logits"))
        print("host_quantized frames = %d" % len(host))
    else:
        host = {}

    # ---- per-frame alignment keyed by frame_id, guarded by input SHA -------
    frames = sorted(set(board) & set(fp32) & (set(host) if host else set(board)))
    frames = [f for f in frames if f in tsha]

    rows = []
    agree_all = 0
    n = len(frames)
    for fid in frames:
        b = board[fid]["raw24"]
        f = fp32[fid]["raw24"]
        h = host[fid]["raw24"] if fid in host else None
        # every backend must have consumed the identical bytes
        assert board[fid]["input_sha256"] == tsha[fid]
        assert fp32[fid]["input_sha256"] == tsha[fid]
        if h is not None:
            assert host[fid]["input_sha256"] == tsha[fid]

        def merged_top1(r24):
            m = merge_logits_24_to_23([float(v) for v in r24])
            idx = int(max(range(len(m)), key=lambda k: m[k]))
            return idx

        bt, ft = merged_top1(b), merged_top1(f)
        ht = merged_top1(h) if h is not None else None

        # confidence = softmax over merged 23, top1 prob
        def conf(r24):
            p = softmax23(r24)
            return float(p.max())

        bc, fc = conf(b), conf(f)
        hc = conf(h) if h is not None else None

        def report_logits(r24):
            return {name: r24[idx] for name, idx in REPORT_CLASSES.items()}

        row = {
            "frame_id": fid,
            "tensor_sha256": tsha[fid],
            "board_npu": {"top1": bt, "class": LABEL_ORDER_24[bt],
                          "confidence": bc, "raw24_top1": int(np.asarray(b).argmax()),
                          "class_logits": report_logits(b)},
            "fp32_onnx": {"top1": ft, "class": LABEL_ORDER_24[ft],
                          "confidence": fc, "raw24_top1": int(np.asarray(f).argmax()),
                          "class_logits": report_logits(f)},
        }
        if h is not None:
            row["host_quantized"] = {"top1": ht, "class": LABEL_ORDER_24[ht],
                                     "confidence": hc,
                                     "raw24_top1": int(np.asarray(h).argmax()),
                                     "class_logits": report_logits(h)}

        stats = {}
        stats["npu_vs_host"] = dict(zip(
            ("max_abs_error", "mean_abs_error", "cosine"), pair_stats(b, h))) if h is not None else None
        stats["host_vs_fp32"] = dict(zip(
            ("max_abs_error", "mean_abs_error", "cosine"), pair_stats(h, f))) if h is not None else None
        stats["npu_vs_fp32"] = dict(zip(
            ("max_abs_error", "mean_abs_error", "cosine"), pair_stats(b, f)))
        row["pairwise"] = stats

        if h is not None:
            row["top1_all_agree"] = (bt == ft == ht)
        else:
            row["top1_all_agree"] = (bt == ft)
        if row["top1_all_agree"]:
            agree_all += 1
        rows.append(row)

    # ---- confusion histogram (merged-23 top1 per backend) ----
    from collections import Counter
    def hist(rows, key):
        return Counter(r[key]["class"] for r in rows)

    hb, hf = hist(rows, "board_npu"), hist(rows, "fp32_onnx")
    hh = hist(rows, "host_quantized") if host else None

    # agreement rates
    def agree(a, b):
        return sum(1 for r in rows if r[a]["top1"] == r[b]["top1"])

    npu_fp32_agree = agree("board_npu", "fp32_onnx")
    npu_host_agree = agree("board_npu", "host_quantized") if host else None
    host_fp32_agree = agree("host_quantized", "fp32_onnx") if host else None

    summary = {
        "num_frames": n,
        "model_json_sha256": mj,
        "model_raw_sha256": mr,
        "params_md5": pmd5,
        "backend_versions": {
            "board_npu": "iCraft ZG330 NPU, compiled bf16 model_24class_ZG",
            "host_quantized": "iCraft v3.39.0 HostBackend (icraft-run --backends Host)",
            "fp32_onnx": "onnxruntime CPU, " + os.path.basename(args.onnx),
        },
        "confusion_histogram": {
            "board_npu": dict(hb),
            "host_quantized": dict(hh) if hh else None,
            "fp32_onnx": dict(hf),
        },
        "agreement": {
            "npu_vs_fp32_top1": "%d/%d" % (npu_fp32_agree, n),
            "npu_vs_host_top1": ("%d/%d" % (npu_host_agree, n)) if host else None,
            "host_vs_fp32_top1": ("%d/%d" % (host_fp32_agree, n)) if host else None,
            "all_three_top1_agree": "%d/%d" % (agree_all, n),
        },
    }

    # ---- judgment ----------------------------------------------------------
    qpsk_any = {}
    for name, key in (("fp32", "fp32_onnx"), ("host", "host_quantized"), ("npu", "board_npu")):
        if key == "host_quantized" and not host:
            qpsk_any[name] = None
            continue
        qpsk_any[name] = sum(1 for r in rows if r[key]["class"] == "QPSK")
    all_qam = all(v == 0 for v in qpsk_any.values() if v is not None)
    verdict = None
    if host and all_qam:
        verdict = ("MODEL_DOMAIN_GENERALIZATION",
                   "FP32 / Host / NPU 三后端全部判 QAM（0×QPSK）：模型在真实域 QPSK 上泛化失败，"
                   "非量化、非编译、非板端 NPU 问题；板端忠实复现了模型本身的错误分类。")
    elif host and qpsk_any["fp32"] > 0 and qpsk_any["host"] == 0 and qpsk_any["npu"] == 0:
        verdict = ("QUANTIZATION_OR_COMPILE",
                   "FP32=QPSK、Host/NPU=QAM：量化或编译引入 QPSK→QAM 跳变。")
    elif host and qpsk_any["fp32"] > 0 and qpsk_any["host"] > 0 and qpsk_any["npu"] == 0:
        verdict = ("BOARD_NPU_RUNTIME",
                   "FP32/Host=QPSK、NPU=QAM：板端 NPU/runtime/input-buffer 问题。")
    elif not host and qpsk_any["fp32"] == 0:
        verdict = ("MODEL_DOMAIN_GENERALIZATION_TENTATIVE",
                   "FP32 与板端 NPU 均判 QAM（0×QPSK）；Host 后端未运行。FP32=QAM 已足以证明"
                   "根因在模型泛化（板端只是忠实复现），但仍建议补 Host 后端做三后端闭合。")
    elif not host and qpsk_any["fp32"] > 0:
        verdict = ("NEEDS_HOST_BACKEND",
                   "FP32=QPSK 但板端 NPU=QAM，需补 Host 后端以区分量化/编译 vs 板端 NPU。")
    else:
        verdict = ("UNSTABLE",
                   "三后端结果不稳定：逐层检查模型身份与 backend 输入。")
    summary["verdict"] = verdict[0]
    summary["verdict_detail"] = verdict[1]

    # ---- report ----
    out_json = os.path.join(args.out_dir, "three_backend_judgment.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "frames": rows}, f, indent=2)

    print()
    print("==== three-backend judgment ====")
    print("frames compared: %d" % n)
    print("confusion histogram (merged-23 top1):")
    for name in ("board_npu", "host_quantized", "fp32_onnx"):
        c = summary["confusion_histogram"][name]
        if c is None:
            print("  %-14s (not run)" % name)
        else:
            print("  %-14s %s" % (name, dict(c)))
    print("agreement:", summary["agreement"])
    print()
    print("VERDICT: %s" % verdict[0])
    print("  %s" % verdict[1])
    print()
    print("wrote %s" % out_json)

    # per-frame table (concise)
    print()
    print("per-frame (frame  top1 NPU/Host/FP32  conf  NPU-vs-FP32 max_abs):")
    for r in rows:
        npu = r["board_npu"]
        fp = r["fp32_onnx"]
        hs = r.get("host_quantized")
        htxt = "%s" % hs["class"] if hs else "-"
        d = r["pairwise"]["npu_vs_fp32"]["max_abs_error"]
        print("  %3d  %-8s %-8s %-8s  %.3f  %.4f"
              % (r["frame_id"], npu["class"], htxt, fp["class"], npu["confidence"], d))

    return 0


if __name__ == "__main__":
    sys.exit(main())
