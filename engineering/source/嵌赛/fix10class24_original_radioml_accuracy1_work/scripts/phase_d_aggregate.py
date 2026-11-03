#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix10class24-original-radioml-accuracy1 — Phase D part 2: aggregate + report data.

Combines Host BF16 (icraft-run) and Host FP32 (torch) per-sample results on the
480-frame frozen stratified ORIGINAL RadioML test selection and produces:

  results/accuracy_by_snr.tsv
  results/accuracy_by_class_snr.tsv
  results/confusion_counts.tsv
  results/bf16_fp32_disagreements.tsv
  results/summary.json

All accuracies are labelled STRATIFIED-SAMPLE TEST ACCURACY (not the entire
RadioML accuracy).  Backends: HOST_BF16 and HOST_FP32_REFERENCE (never board NPU).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

WORK = Path(r"F:/嵌赛/fix10class24_original_radioml_accuracy1_work")
RESULTS = WORK / "results"
INFER = RESULTS / "host_inference"

CLASS_ORDER = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)
SELECT_SNRS = [0, 10, 20, 30]
N_CLASSES = 24
TOTAL = 480
STATUS = "M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-ACCURACY1-COMPLETE"


def fatal(msg: str):
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


def read_tsv(path: Path, header: list[str]) -> dict[int, dict]:
    if not path.is_file():
        fatal("missing %s" % path)
    lines = [ln.rstrip("\r\n") for ln in path.read_text(encoding="utf-8").splitlines()]
    if not lines:
        fatal("empty %s" % path)
    got = lines[0].split("\t")
    if got != header:
        fatal("header mismatch in %s:\n got=%r\n exp=%r" % (path, got, header))
    out = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != len(header):
            fatal("field count mismatch in %s: %r" % (path, ln))
        d = dict(zip(header, f))
        out[int(d["selection_id"])] = d
    if len(out) != TOTAL:
        fatal("%s has %d rows (want %d)" % (path, len(out), TOTAL))
    return out


def main() -> int:
    bf16 = read_tsv(INFER / "per_sample_results.tsv", [
        "selection_id", "hdf5_row_index", "snr_db", "raw24_class", "modulation",
        "split", "pred_pass1", "pred_pass2", "label_correct", "finite",
        "repeat_argmax", "repeat_logits_byte", "top1_logit", "top2_logit", "margin",
        "model_input_sha256", "result_layer",
    ])
    fp32 = read_tsv(INFER / "fp32_per_sample.tsv", [
        "selection_id", "hdf5_row_index", "snr_db", "raw24_class", "modulation",
        "pred", "label_correct", "top1_logit", "top2_logit", "margin", "result_layer",
    ])

    # integrity: same selection ids + same (class, snr) in both
    if set(bf16) != set(fp32):
        fatal("bf16/fp32 selection id sets differ")
    for sid in bf16:
        if bf16[sid]["raw24_class"] != fp32[sid]["raw24_class"]:
            fatal("selection %d class mismatch bf16 vs fp32" % sid)
        if bf16[sid]["snr_db"] != fp32[sid]["snr_db"]:
            fatal("selection %d snr mismatch bf16 vs fp32" % sid)

    sids = sorted(bf16)
    bf16_pred = {sid: int(bf16[sid]["pred_pass1"]) for sid in sids}
    fp32_pred = {sid: int(fp32[sid]["pred"]) for sid in sids}
    true = {sid: int(bf16[sid]["raw24_class"]) for sid in sids}
    snr = {sid: int(bf16[sid]["snr_db"]) for sid in sids}

    bf16_correct = {sid: 1 if bf16_pred[sid] == true[sid] else 0 for sid in sids}
    fp32_correct = {sid: 1 if fp32_pred[sid] == true[sid] else 0 for sid in sids}

    # ---- accuracy_by_snr.tsv ----
    with (RESULTS / "accuracy_by_snr.tsv").open("w", encoding="utf-8", newline="") as f:
        f.write("snr_db\tn_frames\tbf16_correct\tbf16_accuracy\tfp32_correct\tfp32_accuracy\n")
        for s in SELECT_SNRS:
            ids = [sid for sid in sids if snr[sid] == s]
            bc = sum(bf16_correct[sid] for sid in ids)
            fc = sum(fp32_correct[sid] for sid in ids)
            n = len(ids)
            f.write("%d\t%d\t%d\t%.6f\t%d\t%.6f\n" % (s, n, bc, bc / n, fc, fc / n))
        f.write("ALL\t%d\t%d\t%.6f\t%d\t%.6f\n" %
                (TOTAL, sum(bf16_correct.values()), sum(bf16_correct.values()) / TOTAL,
                 sum(fp32_correct.values()), sum(fp32_correct.values()) / TOTAL))

    # ---- accuracy_by_class_snr.tsv ----
    with (RESULTS / "accuracy_by_class_snr.tsv").open("w", encoding="utf-8", newline="") as f:
        hdr = ["raw24_class", "modulation"] + \
              ["%s" % ("bf16_snr%d" % s) for s in SELECT_SNRS] + \
              ["bf16_all"] + \
              ["%s" % ("fp32_snr%d" % s) for s in SELECT_SNRS] + ["fp32_all"]
        f.write("\t".join(hdr) + "\n")
        for c in range(N_CLASSES):
            ids = [sid for sid in sids if true[sid] == c]
            row = [str(c), CLASS_ORDER[c]]
            for s in SELECT_SNRS:
                sub = [sid for sid in ids if snr[sid] == s]
                row.append("%d/%d" % (sum(bf16_correct[sid] for sid in sub), len(sub)))
            row.append("%d/%d" % (sum(bf16_correct[sid] for sid in ids), len(ids)))
            for s in SELECT_SNRS:
                sub = [sid for sid in ids if snr[sid] == s]
                row.append("%d/%d" % (sum(fp32_correct[sid] for sid in sub), len(sub)))
            row.append("%d/%d" % (sum(fp32_correct[sid] for sid in ids), len(ids)))
            f.write("\t".join(row) + "\n")

    # ---- confusion_counts.tsv (BF16, 24x24: rows=true, cols=pred) ----
    conf = np.zeros((N_CLASSES, N_CLASSES), dtype=np.int64)
    for sid in sids:
        conf[true[sid], bf16_pred[sid]] += 1
    with (RESULTS / "confusion_counts.tsv").open("w", encoding="utf-8", newline="") as f:
        f.write("true_class\t" + "\t".join(CLASS_ORDER) + "\n")
        for c in range(N_CLASSES):
            f.write("%s\t" % CLASS_ORDER[c] + "\t".join(str(v) for v in conf[c]) + "\n")

    # ---- bf16_fp32_disagreements.tsv ----
    disc = [sid for sid in sids if bf16_pred[sid] != fp32_pred[sid]]
    with (RESULTS / "bf16_fp32_disagreements.tsv").open("w", encoding="utf-8", newline="") as f:
        f.write("\t".join([
            "selection_id", "hdf5_row_index", "snr_db", "raw24_class", "modulation",
            "bf16_pred", "fp32_pred", "bf16_correct", "fp32_correct",
            "bf16_margin", "fp32_margin",
        ]) + "\n")
        for sid in sorted(disc):
            f.write("\t".join([
                str(sid), bf16[sid]["hdf5_row_index"], str(snr[sid]),
                str(true[sid]), CLASS_ORDER[true[sid]],
                str(bf16_pred[sid]), str(fp32_pred[sid]),
                str(bf16_correct[sid]), str(fp32_correct[sid]),
                bf16[sid]["margin"], fp32[sid]["margin"],
            ]) + "\n")

    # ---- per-class totals (for headline: 64QAM/128QAM/OQPSK/GMSK) ----
    def class_acc(preds_correct, c):
        ids = [sid for sid in sids if true[sid] == c]
        return sum(preds_correct[sid] for sid in ids), len(ids)

    bf16_total_correct = sum(bf16_correct.values())
    fp32_total_correct = sum(fp32_correct.values())

    summary = {
        "task_id": "fix10class24-original-radioml-accuracy1",
        "status": STATUS,
        "backend": "HOST_BF16 (+ HOST_FP32_REFERENCE)",
        "dataset": "RadioML2018.01A ORIGINAL independent TEST split",
        "selection": "stratified {0,10,20,30} dB x 24 classes x 5 = 480 frames, seed 20261019",
        "accuracy_label": "STRATIFIED-SAMPLE TEST ACCURACY (NOT entire RadioML accuracy)",
        "bf16": {
            "correct": bf16_total_correct,
            "total": TOTAL,
            "accuracy": round(bf16_total_correct / TOTAL, 6),
            "result_layer": "HOST_BF16",
        },
        "fp32": {
            "correct": fp32_total_correct,
            "total": TOTAL,
            "accuracy": round(fp32_total_correct / TOTAL, 6),
            "result_layer": "HOST_FP32_REFERENCE",
        },
        "bf16_fp32_disagreements": len(disc),
        "per_class_bf16": {
            CLASS_ORDER[c]: "%d/%d" % class_acc(bf16_correct, c) for c in range(N_CLASSES)
        },
        "focus_classes_bf16": {
            "64QAM": "%d/%d" % class_acc(bf16_correct, 14),
            "128QAM": "%d/%d" % class_acc(bf16_correct, 15),
            "GMSK": "%d/%d" % class_acc(bf16_correct, 22),
            "OQPSK": "%d/%d" % class_acc(bf16_correct, 23),
        },
        "red_lines": [
            "original RadioML HDF5 (not clean24/generated data)",
            "test indices disjoint from train/validation (verified)",
            "480-frame result is stratified-sample test accuracy only",
            "backend HOST_BF16/HOST_FP32_REFERENCE, NOT board NPU",
            "no RF_PASS / PROJECT_COMPLETE",
        ],
    }
    (RESULTS / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("AGGREGATE_OK bf16=%d/%d fp32=%d/%d disagreements=%d" %
          (bf16_total_correct, TOTAL, fp32_total_correct, TOTAL, len(disc)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
