#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix10class24-original-radioml-accuracy1 — Phase D part 1: FP32 reference.

Runs the SAME frozen checkpoint (rml24_seed2027_best.pt, sha 96cd25f8) in FP32
on the 480 selected original RadioML test frames, to compare against the Host
BF16 (icraft-run) predictions and quantify BF16-vs-FP32 argmax disagreement.

Model input contract identical to Phase C:
    X[row] [1024,2] float32 -> [2,1024] fp32 (1024 real then 1024 imag).

Layer = HOST_FP32_REFERENCE (CPU reference).  NOT a board NPU measurement.
Reads HDF5 independently; writes results/host_inference/fp32_per_sample.tsv.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import h5py
import numpy as np
import torch

WORK = Path(r"F:/嵌赛/fix10class24_original_radioml_accuracy1_work")
RESULTS = WORK / "results"
TRAIN_TREE = Path(r"F:/FPGA_Work/sdr_amr_rml24_ood_v1_1")
MODEL_PY = TRAIN_TREE / "models" / "ad_amr_v1_1_net.py"
HDF5_PATH = Path(r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5")
CKPT = Path(r"F:/FPGA_Work/24class_results/rml24_seed2027_best.pt")
CKPT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"

CLASS_ORDER = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)

SEL_HEADER = ["selection_id", "hdf5_row_index", "snr_db", "raw24_class",
              "modulation", "split"]


def fatal(msg: str):
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


def sha256_of(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_model_module():
    spec = importlib.util.spec_from_file_location("ad_amr_v1_1_net", str(MODEL_PY))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_selection(path: Path) -> list[dict]:
    lines = [ln.rstrip("\r\n") for ln in path.read_text(encoding="utf-8").splitlines()]
    header = lines[0].split("\t")
    if header != SEL_HEADER:
        fatal("selection TSV header mismatch: %r" % header)
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        rows.append({
            "selection_id": int(f[0]), "hdf5_row_index": int(f[1]),
            "snr_db": int(f[2]), "raw24_class": int(f[3]), "modulation": f[4],
        })
    if len(rows) != 480:
        fatal("selection TSV has %d rows (want 480)" % len(rows))
    return rows


def main() -> int:
    if sha256_of(CKPT) != CKPT_SHA:
        fatal("checkpoint SHA mismatch (not frozen)")

    net = load_model_module()
    checkpoint = torch.load(CKPT, map_location="cpu", weights_only=False)
    if list(checkpoint.get("class_names", [])) != list(CLASS_ORDER):
        fatal("checkpoint class_names != frozen 24-class order")
    if "model_state" not in checkpoint:
        fatal("checkpoint missing model_state")

    model = net.build_ad_amr_v1_1_model(24)   # config defaults == ADAMRV11Net defaults
    missing, unexpected = model.load_state_dict(checkpoint["model_state"], strict=False)
    if unexpected:
        fatal("load_state_dict unexpected keys: %r" % unexpected)
    model = model.eval()

    sel = read_selection(RESULTS / "frozen_test_selection.tsv")
    h5 = h5py.File(HDF5_PATH, "r")
    try:
        X = h5["X"]
        Y = h5["Y"]
        Z = h5["Z"]
        out_rows = []
        with torch.inference_mode():
            for r in sel:
                row = int(r["hdf5_row_index"])
                x = np.ascontiguousarray(X[row].T).astype(np.float32)
                y_label = int(np.argmax(Y[row]))
                z_val = int(Z[row][0])
                if y_label != r["raw24_class"]:
                    fatal("selection %d HDF5 Y argmax %d != raw24_class %d"
                          % (r["selection_id"], y_label, r["raw24_class"]))
                if z_val != r["snr_db"]:
                    fatal("selection %d HDF5 Z %d != snr_db %d"
                          % (r["selection_id"], z_val, r["snr_db"]))
                t = torch.from_numpy(x).unsqueeze(0)   # [1,2,1024]
                logits, _ = model(t)
                logits = logits[0].to(torch.float64).numpy()
                if not np.all(np.isfinite(logits)):
                    fatal("selection %d FP32 logits non-finite" % r["selection_id"])
                pred = int(np.argmax(logits))
                srt = np.sort(logits)[::-1]
                out_rows.append({
                    "selection_id": r["selection_id"],
                    "hdf5_row_index": r["hdf5_row_index"],
                    "snr_db": r["snr_db"],
                    "raw24_class": r["raw24_class"],
                    "modulation": r["modulation"],
                    "pred": pred,
                    "label_correct": 1 if pred == r["raw24_class"] else 0,
                    "top1_logit": float(srt[0]),
                    "top2_logit": float(srt[1]),
                    "margin": float(srt[0] - srt[1]),
                    "logits": [float(v) for v in logits],
                })
    finally:
        h5.close()

    out_dir = RESULTS / "host_inference"
    out_dir.mkdir(parents=True, exist_ok=True)

    # fp32_per_sample.tsv
    cols = ["selection_id", "hdf5_row_index", "snr_db", "raw24_class",
            "modulation", "pred", "label_correct", "top1_logit", "top2_logit",
            "margin", "result_layer"]
    with (out_dir / "fp32_per_sample.tsv").open("w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in out_rows:
            f.write("\t".join([
                str(r["selection_id"]), str(r["hdf5_row_index"]), str(r["snr_db"]),
                str(r["raw24_class"]), r["modulation"], str(r["pred"]),
                str(r["label_correct"]), "%.9g" % r["top1_logit"],
                "%.9g" % r["top2_logit"], "%.9g" % r["margin"], "HOST_FP32_REFERENCE",
            ]) + "\n")

    # fp32_logits.tsv
    lcols = ["selection_id", "hdf5_row_index", "raw24_class"] + \
            ["logit_%02d" % k for k in range(24)] + ["pred"]
    with (out_dir / "fp32_logits.tsv").open("w", encoding="utf-8", newline="") as f:
        f.write("\t".join(lcols) + "\n")
        for r in out_rows:
            f.write("\t".join([str(r["selection_id"]), str(r["hdf5_row_index"]),
                               str(r["raw24_class"])] +
                              ["%.17g" % v for v in r["logits"]] + [str(r["pred"])]) + "\n")

    n = len(out_rows)
    n_correct = sum(r["label_correct"] for r in out_rows)
    summary = {
        "task_id": "fix10class24-original-radioml-accuracy1",
        "phase": "D_fp32_reference",
        "result_layer": "HOST_FP32_REFERENCE",
        "checkpoint_path": str(CKPT),
        "checkpoint_sha256": CKPT_SHA,
        "checkpoint_epoch": int(checkpoint.get("epoch", -1)),
        "sample_count": n,
        "label_correct": "%d/%d" % (n_correct, n),
        "note": "FP32 CPU reference on ORIGINAL RadioML test frames. NOT board NPU.",
    }
    (out_dir / "fp32_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("FP32_REF_OK samples=%d correct=%d/%d layer=HOST_FP32_REFERENCE epoch=%d"
          % (n, n_correct, n, int(checkpoint.get("epoch", -1))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
