#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""64QAM (and general) Gate 10 precision diagnosis -- decisive 3-way compare.

Reads the error-sample dump written by board_gate10_selftest_12class with
``--dump-error-samples=N --dump-dir=DIR``, then recomputes each dumped MODEL-DOMAIN
input tensor (the exact 2048 fp32 the NPU saw, after receiver_scale) two ways on
the host and compares three argmaxes:

  1. board-NPU      : the argmax the on-chip int8 NPU actually produced (recorded
                      in manifest.tsv as the ``pred`` column + the 12 board logits).
  2. host-ONNX      : ONNX Runtime fp32 on the SAME tensor -- the model's true
                      pre-quantization intent (ground-truth reference).
  3. host fake-INT8 : icraft-run --backends Host --fake_qf on the SAME tensor --
                      the vendor int8 per-channel symmetric (KLD) quantization,
                      run on the host.  This is the exact numeric match to the
                      board's compiled model_12class.json/.raw.

Decisive attribution per sample:
  * onnx correct  AND board wrong AND fake-INT8 == board  -> **int8 quantization
      precision** (a MODEL problem: the fp32 model knows the answer, the int8
      quantization flips it -- hand off to the 12-class robust V2 training, no
      retrain here).
  * onnx correct  AND fake-INT8 correct AND board wrong  -> **board NPU execution**
      (a DEPLOYMENT problem: the host fake path is correct, the chip flips).
  * onnx wrong                                           -> **base fp32 model
      already misclassified** (base-model accuracy, not quantization).
  * fake-INT8 != board                                   -> **quantization/deployment
      divergence** (the host fake path and the chip disagree -- layout/calibration/
      re-arm, see Gate 7 diagnosis).

The tool NEVER changes a threshold, never re-runs the SDR, never picks a seed: it
only compares evidence already captured.  Exit 0 = comparison completed (whatever
the attribution), 1 = fatal (missing dump dir / no manifest / missing executable).

Requires (Windows host): numpy, onnxruntime, and the iCraft CLI 3.39.0
``icraft-run.exe``.  Each missing leg is reported and skipped, so a partial 2-way
compare still runs.

Usage:
  python compare_64qam_threeway.py --dump-dir /path/to/gate10_dump
  python compare_64qam_threeway.py --dump-dir /path/to/dump --onnx <onnx> \
      --json <model.json> --raw <model.raw> --icraft-run <icraft-run.exe>
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np

# Frozen twelve-class order (== cat::target_12(), == deployment_golden class_order).
CLASS_ORDER = [
    "OOK", "4ASK", "AM-DSB", "WBFM", "2FSK", "GFSK",
    "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "OFDM",
]
N_CLASSES = len(CLASS_ORDER)
TENSOR_FLOATS = 2 * 1024  # [2,1024] fp32, C-order (I then Q)

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)


def argmax(vals):
    return int(np.argmax(vals)) if len(vals) else -1


def run_onnx(onnx_path, tensor):
    """Return (logits[12], err).  err is None on success."""
    try:
        import onnxruntime as ort  # noqa: WPS433 (optional, lazy)
    except Exception as e:  # noqa: BLE001
        return None, "onnxruntime not importable: %s" % e
    try:
        sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    except Exception as e:  # noqa: BLE001
        return None, "onnx load failed: %s" % e
    inp = sess.get_inputs()[0].name
    out = sess.get_outputs()[0].name
    x = tensor.reshape(1, 2, 1024).astype(np.float32)
    try:
        logits = sess.run([out], {inp: x})[0][0]
    except Exception as e:  # noqa: BLE001
        return None, "onnx run failed: %s" % e
    return np.asarray(logits, dtype=np.float64), None


def run_fake_qf(icraft_run, json_path, raw_path, tensor_file, log_dir):
    """Run icraft-run --fake_qf on one .bin; return (logits[12], err)."""
    base = os.path.splitext(os.path.basename(json_path))[0]
    ftmp = os.path.join(log_dir, base, "ftmpSFT", "922.ftmp")
    if os.path.exists(ftmp):
        os.remove(ftmp)
    cmd = [
        icraft_run,
        "--json", json_path,
        "--raw", raw_path,
        "--input", tensor_file,
        "--backends", "Host",
        "--fake_qf",
        "--dump_format", "SFT",
        "--dump_ftmp", "922",
        "--log_path", log_dir,
    ]
    with open(os.devnull, "w") as devnull:
        subprocess.run(cmd, stdout=devnull, stderr=devnull, check=False)
    if not os.path.exists(ftmp):
        return None, "icraft-run produced no %s (exit/backends/fake_qf?)" % ftmp
    try:
        vals = [float(x) for x in open(ftmp, encoding="utf-8").read().split()]
    except Exception as e:  # noqa: BLE001
        return None, "could not read %s: %s" % (ftmp, e)
    if len(vals) != N_CLASSES:
        return None, "fake_qf logits len=%d (want %d)" % (len(vals), N_CLASSES)
    return np.asarray(vals, dtype=np.float64), None


def read_manifest(dump_dir):
    """Return list of dicts, one per dumped sample, with the board's own logits."""
    mpath = os.path.join(dump_dir, "manifest.tsv")
    if not os.path.isfile(mpath):
        return None
    rows = []
    with open(mpath, encoding="utf-8") as f:
        header = None
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            fields = line.split("\t")
            if header is None:
                header = fields
                continue
            if len(fields) < 7 + N_CLASSES:
                continue
            seq = int(fields[0])
            ref = int(fields[1])
            pred = int(fields[3])
            seed = fields[5]
            crc = fields[6]
            board_logits = np.asarray([float(x) for x in fields[7:7 + N_CLASSES]],
                                      dtype=np.float64)
            rows.append({
                "seq": seq, "ref": ref, "pred": pred, "seed": seed, "crc": crc,
                "board_logits": board_logits,
                "bin": os.path.join(dump_dir, "error_%03d.bin" % seq),
            })
    return rows


def load_tensor(path):
    arr = np.fromfile(path, dtype=np.float32)
    if arr.size != TENSOR_FLOATS:
        return None
    return arr.astype(np.float64)


def attribution(onnx_pred, fake_pred, board_pred, ref):
    """Return the decisive category string for one sample."""
    onnx_correct = onnx_pred == ref
    fake_correct = fake_pred == ref
    board_correct = board_pred == ref
    if onnx_correct and not board_correct and (fake_pred == board_pred):
        return "INT8_QUANTIZATION_PRECISION"
    if onnx_correct and fake_correct and not board_correct:
        return "BOARD_NPU_EXECUTION"
    if not onnx_correct:
        return "BASE_FP32_MISCLASSIFY"
    if fake_pred != board_pred:
        return "QUANT_DEPLOYMENT_DIVERGENCE"
    if board_correct:
        return "BOARD_CORRECT"  # (should not appear in an error dump, but be total)
    return "UNCLASSIFIED"


def main():
    ap = argparse.ArgumentParser(description="64QAM / Gate 10 precision 3-way compare")
    ap.add_argument("--dump-dir", required=True, help="dir written by --dump-dir on the board")
    ap.add_argument("--onnx", default=os.path.join(
        PKG, "..", "_tmp_ad_amr_results_verify",
        "ad_amr_data_v3_12class_ff2b3fb3_run", "outputs", "ad_amr_v1_1_data_v3_12class",
        "formal", "export", "onnx", "ad_amr_v1_1_opset17.onnx"))
    ap.add_argument("--json", default=os.path.join(PKG, "model_12class", "model_12class.json"))
    ap.add_argument("--raw", default=os.path.join(PKG, "model_12class", "model_12class.raw"))
    ap.add_argument("--icraft-run",
                    default=r"C:\Icraft\CLI v3.39.0\bin\icraft-run.exe")
    args = ap.parse_args()

    if not os.path.isdir(args.dump_dir):
        print("FATAL: dump dir not found: %s" % args.dump_dir)
        return 1
    rows = read_manifest(args.dump_dir)
    if rows is None:
        print("FATAL: %s/manifest.tsv not found or empty" % args.dump_dir)
        return 1
    if not rows:
        print("FATAL: no error samples recorded (manifest empty)")
        return 1

    onnx_ok = os.path.isfile(args.onnx)
    fake_ok = os.path.isfile(args.icraft_run) and os.path.isfile(args.json) \
        and os.path.isfile(args.raw)
    if not onnx_ok:
        print("WARN: ONNX not found at %s -> ONNX leg skipped" % args.onnx)
    if not fake_ok:
        print("WARN: icraft-run / model artifacts missing -> fake-INT8 leg skipped")

    log_dir = tempfile.mkdtemp(prefix="icraft_qf_")

    counts = {}
    print("=== 3-WAY COMPARE (ref -> board/onnx/fake) ===")
    print("dump_dir=%s samples=%d" % (args.dump_dir, len(rows)))
    print("class_order=%s" % ",".join(CLASS_ORDER))

    for r in rows:
        seq, ref, board_pred = r["seq"], r["ref"], r["pred"]
        board_logits = r["board_logits"]
        tensor = load_tensor(r["bin"])
        if tensor is None:
            print("[%03d] ERROR: missing/invalid tensor %s" % (seq, r["bin"]))
            continue

        onnx_logits = onnx_pred = None
        if onnx_ok:
            onnx_logits, err = run_onnx(args.onnx, tensor)
            if err:
                print("[%03d] ONNX ERROR: %s" % (seq, err))
            else:
                onnx_pred = argmax(onnx_logits)

        fake_logits = fake_pred = None
        if fake_ok:
            fake_logits, err = run_fake_qf(args.icraft_run, args.json, args.raw,
                                           r["bin"], log_dir)
            if err:
                print("[%03d] FAKE-QF ERROR: %s" % (seq, err))
            else:
                fake_pred = argmax(fake_logits)

        cat = attribution(onnx_pred, fake_pred, board_pred, ref)

        def nm(x):
            return CLASS_ORDER[x] if x is not None else "-"

        line = ("[%03d] ref=%d(%s) board=%d(%s) onnx=%s(%s) fake=%s(%s) -> %s"
                % (seq, ref, nm(ref), board_pred, nm(board_pred),
                   onnx_pred if onnx_pred is not None else "-", nm(onnx_pred),
                   fake_pred if fake_pred is not None else "-", nm(fake_pred),
                   cat))
        print(line)

        # logit agreement (decides quantization vs execution)
        if fake_logits is not None:
            d = float(np.max(np.abs(fake_logits - board_logits)))
            print("      |board-fake|max=%.6g" % d)
        if onnx_logits is not None:
            d = float(np.max(np.abs(onnx_logits - board_logits)))
            print("      |board-onnx|max=%.6g  board_logits=%s"
                  % (d, np.array2string(board_logits, precision=4)))
        counts[cat] = counts.get(cat, 0) + 1

    print("\n=== ATTRIBUTION SUMMARY ===")
    for k in sorted(counts):
        print("  %-28s %d" % (k, counts[k]))

    # Decisive overall verdict.
    total = sum(counts.values())
    if total == 0:
        print("NO verdict: no sample compared")
        return 1
    if counts.get("INT8_QUANTIZATION_PRECISION", 0) == total:
        print("VERDICT: int8 quantization precision (fp32 correct, fake-INT8 "
              "reproduces the board flip) -> MODEL problem, hand off to 12-class "
              "robust V2 training (no retrain/replace here).")
    elif counts.get("BOARD_NPU_EXECUTION", 0) == total:
        print("VERDICT: board NPU execution (fp32 AND fake-INT8 correct, chip "
              "flips) -> DEPLOYMENT problem, see Gate 7 re-arm/layout diagnosis.")
    elif counts.get("BASE_FP32_MISCLASSIFY", 0) == total:
        print("VERDICT: base fp32 model already misclassifies these samples -> "
              "base-model accuracy, not quantization.")
    elif counts.get("QUANT_DEPLOYMENT_DIVERGENCE", 0) == total:
        print("VERDICT: fake-INT8 and board NPU disagree -> quantization/deployment "
              "divergence, investigate layout/calibration/re-arm.")
    else:
        print("VERDICT: MIXED (%s) -- see per-sample lines." % "/".join(sorted(counts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
