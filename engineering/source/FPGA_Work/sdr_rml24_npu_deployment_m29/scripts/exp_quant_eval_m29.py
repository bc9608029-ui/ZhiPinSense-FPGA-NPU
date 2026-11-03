#!/usr/bin/env python
"""M29 Phase D.1 — comprehensive quantized-model evaluation (icraft-run Host).

Runs a generated NPU model (e.g. Experiment A: front INT8 + head BF16) on the
bounded 1536-sample validation subset and reports the full remediation metric
set required by the Phase D.1 promotion gate:

  * accuracy / macro-F1 / rated_0_20 / snr0 / min_class
  * AM-SSB-SC overall accuracy + 12-30 dB accuracy
  * AM-SSB-SC -> AM-SSB-WC / OOK confusion counts
  * Top-1 agreement (quantized vs fp32)
  * logits top1-top2 margin distribution (all samples + AM-SSB-SC samples)

This is a READ-ONLY evaluation: it reads the validation subset (never test),
writes per-sample I/Q to a throwaway work dir, and saves logits/preds + a
JSON report to a fresh experiment output dir.

Usage:
  python exp_quant_eval_m29.py --json <ZG.json> --raw <ZG.raw> \
      --work-dir <dir> --out-dir <dir> --label expA
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

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402

ROOT = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29"
HDF5_PATH = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"
ICRAFT_RUN = r"D:\icraft\bin\icraft-run.exe"
SUBSET = os.path.join(ROOT, "work", "eval_full", "subset_index.npz")

LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)
AM_SSB_WC, AM_SSB_SC, OOK = 17, 18, 0


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def _summary(targets, predictions, snrs, num_classes: int) -> dict:
    targets = np.asarray(targets, dtype=np.int64)
    predictions = np.asarray(predictions, dtype=np.int64)
    snrs = np.asarray(snrs, dtype=np.float32)
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    np.add.at(cm, (targets, predictions), 1)
    row_sum = cm.sum(axis=1)
    per_class = np.divide(np.diag(cm), row_sum, out=np.zeros(num_classes, dtype=float),
                          where=row_sum > 0)
    correct = (predictions == targets)
    accuracy = float(correct.mean())

    def slice_accuracy(predicate) -> float:
        sel = correct[predicate(snrs)]
        return float(sel.mean()) if len(sel) else 0.0

    f1s = []
    for c in range(num_classes):
        tp = cm[c, c]
        fp = cm[:, c].sum() - tp
        fn = row_sum[c] - tp
        f1s.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0.0)
    return {
        "accuracy": accuracy,
        "macro_f1": float(np.mean(f1s)),
        "per_class_accuracy": [float(v) for v in per_class],
        "min_per_class_accuracy": float(per_class.min()),
        "min_class_idx": int(per_class.argmin()),
        "min_class_name": LABEL_ORDER_24[int(per_class.argmin())],
        "rated_0_20_accuracy": slice_accuracy(lambda s: (s >= 0.0) & (s <= 20.0)),
        "snr_0_accuracy": slice_accuracy(lambda s: s == 0.0),
    }


def _confusion(targets, predictions, snrs):
    """AM-SSB-SC (class 18) confusion breakdown."""
    targets = np.asarray(targets, dtype=np.int64)
    predictions = np.asarray(predictions, dtype=np.int64)
    snrs = np.asarray(snrs, dtype=np.float32)
    m = targets == AM_SSB_SC
    pred = predictions[m]
    s = snrs[m]
    correct = (pred == AM_SSB_SC).sum()
    wc = (pred == AM_SSB_WC).sum()
    ook = (pred == OOK).sum()
    other = (~np.isin(pred, [AM_SSB_SC, AM_SSB_WC, OOK])).sum()
    tot = int(m.sum())
    hi = s >= 12.0
    hi_pred = pred[hi]
    return {
        "total": tot,
        "correct": int(correct),
        "correct_rate": float(correct / tot) if tot else 0.0,
        "to_AM_SSB_WC": int(wc),
        "to_OOK": int(ook),
        "to_other": int(other),
        "high_snr_12_30": {
            "total": int(hi.sum()),
            "correct": int((hi_pred == AM_SSB_SC).sum()),
            "correct_rate": float((hi_pred == AM_SSB_SC).mean()) if hi.sum() else 0.0,
        },
    }


def _margin_dist(logits: np.ndarray) -> dict:
    s = np.sort(logits, axis=1)
    margin = s[:, -1] - s[:, -2]
    return {
        "min": float(margin.min()),
        "median": float(np.median(margin)),
        "mean": float(margin.mean()),
        "p90": float(np.percentile(margin, 90)),
        "p99": float(np.percentile(margin, 99)),
        "max": float(margin.max()),
    }


def _run_one(work_dir, in_bin: str) -> np.ndarray:
    ftmp_dir = os.path.join(work_dir, ".icraft", "logs", "model_24class", "ftmpHQB")
    for old in glob.glob(os.path.join(ftmp_dir, "*.ftmp")):
        os.remove(old)
    cmd = [ICRAFT_RUN, "--json", ARGS.json, "--raw", ARGS.raw, "--network", "model_24class",
           "--input", in_bin, "--backends", "Host", "--dump_output"]
    subprocess.run(cmd, cwd=work_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   check=True, timeout=120)
    ftmps = glob.glob(os.path.join(ftmp_dir, "*.ftmp"))
    if not ftmps:
        raise RuntimeError(f"no output ftmp for {in_bin}")
    logits = np.fromfile(ftmps[0], dtype=np.float32)
    if logits.size != 24:
        raise RuntimeError(f"unexpected output size {logits.size} for {in_bin}")
    return logits


def main() -> int:
    print(f"== M29 Phase D.1 quantized eval: {ARGS.label} ==")
    print(f"  json = {ARGS.json}")
    print(f"  raw  = {ARGS.raw}")
    if not os.path.exists(ARGS.json) or not os.path.exists(ARGS.raw):
        print("  FAIL: model json/raw missing"); return 1
    print(f"  json sha = {sha256_file(ARGS.json)}")
    print(f"  raw  sha = {sha256_file(ARGS.raw)}")

    with np.load(SUBSET, allow_pickle=False) as z:
        sub_indices = z["sub_indices"].astype(np.int64)
        sub_labels = z["sub_labels"].astype(np.int64)
        sub_snrs = z["sub_snrs"].astype(np.float32)
        sub_fp32 = z["sub_fp32"].astype(np.int64)
    n = len(sub_indices)
    print(f"  subset = {n} samples (validation, NOT test)")

    os.makedirs(ARGS.work_dir, exist_ok=True)
    import h5py
    quant_pred = np.empty(n, dtype=np.int64)
    quant_logits = np.empty((n, 24), dtype=np.float32)
    t0 = time.time()
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for i, src in enumerate(sub_indices.tolist()):
            raw = np.asarray(X[src], dtype=np.float32)
            planar = np.ascontiguousarray(raw.T)
            in_bin = os.path.join(ARGS.work_dir, f"iq_{i}.bin")
            planar.tofile(in_bin)
            logits = _run_one(ARGS.work_dir, in_bin)
            quant_logits[i] = logits
            quant_pred[i] = int(logits.argmax())
            if (i + 1) % 64 == 0 or (i + 1) == n:
                rate = (i + 1) / (time.time() - t0)
                eta = (n - i - 1) / rate if rate > 0 else 0.0
                print(f"  [{i + 1}/{n}] rate={rate:.2f} samp/s  ETA={eta/60:.1f} min")

    agree = float((quant_pred == sub_fp32).mean())
    q = _summary(sub_labels, quant_pred, sub_snrs, 24)
    f = _summary(sub_labels, sub_fp32, sub_snrs, 24)
    conf = _confusion(sub_labels, quant_pred, sub_snrs)
    margin_all = _margin_dist(quant_logits)
    sc_mask = sub_labels == AM_SSB_SC
    margin_sc = _margin_dist(quant_logits[sc_mask])
    print(f"\n  quantized acc={q['accuracy']:.6f} (fp32 same subset={f['accuracy']:.6f})")
    print(f"  Top-1 agreement (quant vs fp32) = {agree:.6f}")
    print(f"  AM-SSB-SC acc={conf['correct_rate']:.4f}  12-30dB acc={conf['high_snr_12_30']['correct_rate']:.4f}")

    os.makedirs(ARGS.out_dir, exist_ok=True)
    np.save(os.path.join(ARGS.out_dir, f"{ARGS.label}_preds.npy"), quant_pred)
    np.save(os.path.join(ARGS.out_dir, f"{ARGS.label}_logits.npy"), quant_logits)
    report = {
        "phase": "M29-Phase-D.1-quantization-remediation",
        "experiment": ARGS.label,
        "model_json_sha": sha256_file(ARGS.json),
        "model_raw_sha": sha256_file(ARGS.raw),
        "backends": "Host",
        "split": "radioml2018_validation",
        "test_split_touched": False,
        "subset_per_class": 64,
        "subset_size": int(n),
        "label_order": list(LABEL_ORDER_24),
        "quantized": q,
        "fp32_on_same_subset": f,
        "top1_agreement_quant_vs_fp32": agree,
        "accuracy_drop": f["accuracy"] - q["accuracy"],
        "macro_f1_drop": f["macro_f1"] - q["macro_f1"],
        "rated_0_20_drop": f["rated_0_20_accuracy"] - q["rated_0_20_accuracy"],
        "snr0_drop": f["snr_0_accuracy"] - q["snr_0_accuracy"],
        "min_class_drop": f["min_per_class_accuracy"] - q["min_per_class_accuracy"],
        "am_ssb_sc_confusion": conf,
        "logits_margin_all": margin_all,
        "logits_margin_am_ssb_sc": margin_sc,
    }
    out_report = os.path.join(ARGS.out_dir, f"{ARGS.label}_report.json")
    with open(out_report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"  wrote {out_report}")
    print(f"== M29 {ARGS.label} quantized eval PASS ==")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", required=True)
    ARGS = ap.parse_args()
    sys.exit(main())
