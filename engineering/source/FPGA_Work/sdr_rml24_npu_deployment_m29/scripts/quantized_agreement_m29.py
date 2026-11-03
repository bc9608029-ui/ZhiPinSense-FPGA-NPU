#!/usr/bin/env python
"""M29 Phase D — ACTUAL vendor INT8 model evaluation via icraft-run (Host backend).

Runs the real generated NPU model (model_24class_ZG.json/.raw) on a bounded
stratified validation subset and compares its Top-1 argmax against the fp32
checkpoint predictions + true labels saved by full_validation_eval_m29.py.

This is the faithful "量化模型" measurement: weights + activations + output are
all vendor INT8 (per-channel KLD).  One icraft-run process per sample (~1.3 s),
so this is a BOUNDED subset, not the full 511,056-sample split.

Reports:
  * quantized Top-1 agreement vs fp32  (label-order / export-faithfulness check)
  * quantized accuracy / macro-F1 / rated_0_20 / snr0 / min_class (subset estimate)
  * per-sample logits saved for audit

Writes work/eval_quant/{quant_preds.npy, quant_logits.npy,
quantized_agreement_report.json} + artifacts/m29_quantized_agreement_report.json.
"""
from __future__ import annotations

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
ZG_JSON = r"F:\FPGA_Work\_tmp_24class_adapt_generate_384_20261010\jsonraw\model_24class_ZG.json"
ZG_RAW = r"F:\FPGA_Work\_tmp_24class_adapt_generate_384_20261010\jsonraw\model_24class_ZG.raw"
ICRAFT_RUN = r"D:\icraft\bin\icraft-run.exe"
WORK_DIR = r"F:\FPGA_Work\_tmp_24class_adapt_generate_384_20261010\runloop"

LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)


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
        "rated_0_20_accuracy": slice_accuracy(lambda s: (s >= 0.0) & (s <= 20.0)),
        "snr_0_accuracy": slice_accuracy(lambda s: s == 0.0),
    }


def _run_one(input_bin: str) -> np.ndarray:
    """Run icraft-run on one sample, return the 24-dim fp32 logits."""
    ftmp = os.path.join(WORK_DIR, ".icraft", "logs", "model_24class", "ftmpHQB", "922.ftmp")
    if os.path.exists(ftmp):
        os.remove(ftmp)
    cmd = [ICRAFT_RUN, "--json", ZG_JSON, "--raw", ZG_RAW, "--network", "model_24class",
           "--input", input_bin, "--backends", "Host", "--dump_output"]
    subprocess.run(cmd, cwd=WORK_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   check=True, timeout=120)
    if not os.path.exists(ftmp):
        raise RuntimeError(f"no output ftmp for {input_bin}")
    logits = np.fromfile(ftmp, dtype=np.float32)
    if logits.size != 24:
        raise RuntimeError(f"unexpected output size {logits.size} for {input_bin}")
    return logits


def main() -> int:
    print("== M29 Phase D: ACTUAL vendor INT8 model evaluation (icraft-run Host) ==")
    subset_path = os.path.join(ROOT, "work", "eval_full", "subset_index.npz")
    if not os.path.exists(subset_path):
        print(f"  FAIL: {subset_path} missing (run full_validation_eval_m29.py first)")
        return 1
    with np.load(subset_path, allow_pickle=False) as z:
        sub_indices = z["sub_indices"].astype(np.int64)
        sub_labels = z["sub_labels"].astype(np.int64)
        sub_snrs = z["sub_snrs"].astype(np.float32)
        sub_fp32 = z["sub_fp32"].astype(np.int64)
    n = len(sub_indices)
    print(f"  subset = {n} samples; ZG model json/raw SHA below")
    import hashlib
    for p in (ZG_JSON, ZG_RAW):
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 22), b""):
                h.update(chunk)
        print(f"  {os.path.basename(p)} sha256 = {h.hexdigest()}")

    os.makedirs(WORK_DIR, exist_ok=True)
    import h5py
    quant_pred = np.empty(n, dtype=np.int64)
    quant_logits = np.empty((n, 24), dtype=np.float32)
    t0 = time.time()
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for i, src in enumerate(sub_indices.tolist()):
            raw = np.asarray(X[src], dtype=np.float32)          # [1024, 2]
            planar = np.ascontiguousarray(raw.T)                # [2, 1024] C-order
            in_bin = os.path.join(WORK_DIR, f"iq_{i}.bin")
            planar.tofile(in_bin)
            logits = _run_one(in_bin)
            quant_logits[i] = logits
            quant_pred[i] = int(logits.argmax())
            if (i + 1) % 64 == 0 or (i + 1) == n:
                rate = (i + 1) / (time.time() - t0)
                eta = (n - i - 1) / rate if rate > 0 else 0.0
                print(f"  [{i + 1}/{n}] rate={rate:.2f} samples/s  ETA={eta/60:.1f} min")

    agree = float((quant_pred == sub_fp32).mean())
    int8_agree_note = ""  # agreement vs fake-INT8 computed from saved sub_int8 below if present
    quant_sum = _summary(sub_labels, quant_pred, sub_snrs, 24)
    fp32_sum = _summary(sub_labels, sub_fp32, sub_snrs, 24)
    print(f"\n  quantized acc={quant_sum['accuracy']:.6f} (fp32 on same subset={fp32_sum['accuracy']:.6f})")
    print(f"  Top-1 agreement (quant vs fp32) = {agree:.6f}")

    out_dir = os.path.join(ROOT, "work", "eval_quant")
    os.makedirs(out_dir, exist_ok=True)
    np.save(os.path.join(out_dir, "quant_preds.npy"), quant_pred)
    np.save(os.path.join(out_dir, "quant_logits.npy"), quant_logits)
    report = {
        "phase": "M29-Phase-D-actual-vendor-int8-icraft-run",
        "model_artifact": "model_24class_ZG",
        "backends": "Host",
        "split": "radioml2018_validation",
        "test_split_touched": False,
        "subset_per_class": 64,
        "subset_size": int(n),
        "label_order": list(LABEL_ORDER_24),
        "quantized": {k: v for k, v in quant_sum.items() if k != "confusion_matrix"},
        "fp32_on_same_subset": {k: v for k, v in fp32_sum.items() if k != "confusion_matrix"},
        "top1_agreement_quant_vs_fp32": agree,
        "accuracy_drop": fp32_sum["accuracy"] - quant_sum["accuracy"],
        "macro_f1_drop": fp32_sum["macro_f1"] - quant_sum["macro_f1"],
        "rated_0_20_drop": fp32_sum["rated_0_20_accuracy"] - quant_sum["rated_0_20_accuracy"],
        "snr0_drop": fp32_sum["snr_0_accuracy"] - quant_sum["snr_0_accuracy"],
        "min_class_drop": fp32_sum["min_per_class_accuracy"] - quant_sum["min_per_class_accuracy"],
    }
    for path in (os.path.join(out_dir, "quantized_agreement_report.json"),
                 os.path.join(ROOT, "artifacts", "m29_quantized_agreement_report.json")):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"  wrote {path}")
    print("== M29 actual-quantized agreement eval PASS ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
