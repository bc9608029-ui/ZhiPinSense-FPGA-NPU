#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix10class24-original-radioml-accuracy1 — Phase A (identity/contract) + Phase B
(frozen stratified test selection).

Pure offline, read-only on all inputs.  Verifies:
  * HDF5 identity (audit.json sha + size + mtime_ns; avoids a 21 GiB full rehash)
  * split index SHA, checkpoint SHA, BF16 model json/raw SHA
  * test_indices are unique and disjoint from train/validation
  * labels/snrs consistent with the frozen 24-class order and SNR grid

Then deterministically selects 480 frames = {0,10,20,30} dB x 24 classes x 5
from the TEST split, records the seed + original HDF5 row indices, freezes the
selection (TSV + SHA) BEFORE any inference.

Writes: results/dataset_identity.json, results/training_input_contract.json,
        results/frozen_test_selection.tsv (+ .sha256).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

WORK = Path(r"F:/嵌赛/fix10class24_original_radioml_accuracy1_work")
RESULTS = WORK / "results"
TRAIN_TREE = Path(r"F:/FPGA_Work/sdr_amr_rml24_ood_v1_1")
DATA = TRAIN_TREE / "data" / "radioml2018"
MODEL_TREE = Path(r"F:/嵌赛/fix10class24_tx_rms_sweep1_work/sdr_rml24_fix10class24_tx_rms_sweep1/model_rml24_bf16")

HDF5 = Path(r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5")
AUDIT_JSON = DATA / "audit.json"
CLASSES_TXT = DATA / "classes.txt"
SPLIT_NPZ = DATA / "rml24_split_indices.npz"
CKPT = Path(r"F:/FPGA_Work/24class_results/rml24_seed2027_best.pt")
MODEL_JSON = MODEL_TREE / "rml24_adamrv11_bf16.json"
MODEL_RAW = MODEL_TREE / "rml24_adamrv11_bf16.raw"

HDF5_SHA = "e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38"
SPLIT_SHA = "9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335"
CKPT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"
MODEL_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
MODEL_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

CLASS_ORDER = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)

SNR_GRID = list(range(-20, 31, 2))          # 26 values
SELECT_SNRS = [0, 10, 20, 30]
PER_CLASS = 5
SELECT_SEED = 20261019                       # deterministic selection seed

STATUS = "M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-ACCURACY1-COMPLETE"


def fatal(msg: str) -> "NoReturn":
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_identities() -> dict:
    audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    if audit.get("status") != "pass" or audit.get("dataset") != "RadioML2018.01A":
        fatal("audit.json not a passing RadioML2018.01A audit")

    st = HDF5.stat()
    # identity via audited sha + size + mtime_ns (21 GiB full rehash skipped; the
    # audit.json sha is the frozen authority recorded at data-audit time).
    if audit.get("size_bytes") != st.st_size:
        fatal("HDF5 size %d != audited %d" % (st.st_size, audit.get("size_bytes")))
    if audit.get("mtime_ns") != st.st_mtime_ns:
        fatal("HDF5 mtime_ns %d != audited %d" % (st.st_mtime_ns, audit.get("mtime_ns")))
    if audit.get("sha256") != HDF5_SHA:
        fatal("HDF5 audit sha %s != frozen %s" % (audit.get("sha256"), HDF5_SHA))
    if audit.get("class_names") != list(CLASS_ORDER):
        fatal("audit class_names != frozen 24-class order")
    if audit.get("samples") != 2555904:
        fatal("audit samples != 2555904")

    if sha256_file(SPLIT_NPZ) != SPLIT_SHA:
        fatal("split npz SHA mismatch")
    if sha256_file(CKPT) != CKPT_SHA:
        fatal("checkpoint SHA mismatch")
    if sha256_file(MODEL_JSON) != MODEL_JSON_SHA:
        fatal("model json SHA mismatch")
    if sha256_file(MODEL_RAW) != MODEL_RAW_SHA:
        fatal("model raw SHA mismatch")

    classes = tuple(
        ln.strip().strip("'\",") for ln in CLASSES_TXT.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    )
    if classes != CLASS_ORDER:
        fatal("classes.txt != frozen 24-class order")

    return {
        "hdf5_path": str(HDF5),
        "hdf5_size_bytes": st.st_size,
        "hdf5_mtime_ns": st.st_mtime_ns,
        "hdf5_sha256": HDF5_SHA,
        "hdf5_sha_method": "audit.json (frozen at data-audit) + size + mtime_ns; full rehash skipped for 21 GiB",
        "hdf5_samples": audit.get("samples"),
        "hdf5_X_shape": [2555904, 1024, 2],
        "hdf5_X_dtype": "float32",
        "hdf5_Y_shape": [2555904, 24],
        "hdf5_Z_shape": [2555904, 1],
        "split_seed": audit.get("split_seed"),
        "split_ratios": audit.get("split_ratios"),
        "split_counts": audit.get("split_counts"),
        "split_index_sha256": SPLIT_SHA,
        "snr_grid": SNR_GRID,
        "class_order": list(CLASS_ORDER),
        "checkpoint_path": str(CKPT),
        "checkpoint_sha256": CKPT_SHA,
    }


def load_splits() -> dict:
    z = np.load(SPLIT_NPZ, allow_pickle=False)
    out = {}
    for split in ("train", "validation", "test"):
        idx = z[f"{split}_indices"].astype(np.int64)
        lab = z[f"{split}_labels"].astype(np.int64)
        snr = z[f"{split}_snrs"].astype(np.float64)
        if not (len(idx) == len(lab) == len(snr)):
            fatal(f"{split} arrays length mismatch")
        if len(np.unique(idx)) != len(idx):
            fatal(f"{split} indices not unique")
        if lab.min() < 0 or lab.max() > 23:
            fatal(f"{split} labels out of 0..23")
        out[split] = {"idx": idx, "lab": lab, "snr": snr}
    # train/test/validation disjointness
    ti = set(out["test"]["idx"].tolist())
    tr = set(out["train"]["idx"].tolist())
    va = set(out["validation"]["idx"].tolist())
    if ti & tr:
        fatal("test ∩ train != empty")
    if ti & va:
        fatal("test ∩ validation != empty")
    if tr & va:
        fatal("train ∩ validation != empty")
    return out


def select_frames(splits: dict) -> list[dict]:
    test = splits["test"]
    rng = np.random.default_rng(SELECT_SEED)
    rows = []
    for snr in SELECT_SNRS:
        for cidx, name in enumerate(CLASS_ORDER):
            pos = np.flatnonzero((test["lab"] == cidx) & (np.isclose(test["snr"], snr)))
            if len(pos) < PER_CLASS:
                fatal(f"stratum (class={name}, snr={snr}) has {len(pos)} < {PER_CLASS} test frames")
            order = rng.permutation(len(pos))
            chosen = pos[order[:PER_CLASS]]
            hdf5_rows = test["idx"][chosen]
            for k in range(PER_CLASS):
                rows.append({
                    "snr_db": snr,
                    "raw24_class": cidx,
                    "modulation": name,
                    "hdf5_row_index": int(hdf5_rows[k]),
                })
    # uniqueness + no train cross (re-check on the concrete selection)
    sel_idx = [r["hdf5_row_index"] for r in rows]
    if len(set(sel_idx)) != len(sel_idx):
        fatal("selected hdf5 rows not unique")
    tr_set = set(splits["train"]["idx"].tolist())
    if set(sel_idx) & tr_set:
        fatal("selected rows intersect train split")
    return rows


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    ident = verify_identities()

    # dataset_identity.json
    (RESULTS / "dataset_identity.json").write_text(
        json.dumps(ident, indent=2, sort_keys=True), encoding="utf-8")

    # training_input_contract.json
    contract = {
        "task_id": "fix10class24-original-radioml-accuracy1",
        "model": "ADAMRV11Net num_classes=24 (frozen BF16)",
        "source_preprocessing": (
            "RadioML2018Dataset.__getitem__ (datasets/radioml2018_dataset.py): "
            "raw = X[source_index] [1024,2] float32 -> "
            "torch.from_numpy(np.ascontiguousarray(raw.T)) = [2,1024] float32 "
            "(row0=real, row1=imag)."),
        "dc_handling": "none (no DC removal)",
        "normalization": "none (raw HDF5 values, per-class RMS NOT uniform)",
        "resampling": "none",
        "filtering": "none",
        "augmentation": "none (rml24.apply_channel_augmentation=false)",
        "input_layout": "channels-first [2,1024]: 1024 real f32 then 1024 imag f32, little-endian",
        "input_bytes": 8192,
        "input_dtype": "fp32",
        "network_name": "model_24class",
        "network_input_shape": [1, 2, 1024],
        "network_output_shape": [1, 24],
        "model_json_sha256": MODEL_JSON_SHA,
        "model_raw_sha256": MODEL_RAW_SHA,
        "fp32_checkpoint_path": str(CKPT),
        "fp32_checkpoint_sha256": CKPT_SHA,
        "label_order": list(CLASS_ORDER),
        "note": "AM-SSB-WC (17) and AM-SSB-SC (18) are independent raw24 classes.",
    }
    (RESULTS / "training_input_contract.json").write_text(
        json.dumps(contract, indent=2, sort_keys=True), encoding="utf-8")

    # selection
    splits = load_splits()
    frames = select_frames(splits)
    assert len(frames) == len(SELECT_SNRS) * 24 * PER_CLASS == 480, len(frames)

    header = ["selection_id", "hdf5_row_index", "snr_db", "raw24_class",
              "modulation", "split"]
    lines = [header]
    for i, r in enumerate(frames):
        lines.append([str(i + 1), str(r["hdf5_row_index"]), str(r["snr_db"]),
                      str(r["raw24_class"]), r["modulation"], "test"])
    tsv_text = "\n".join("\t".join(row) for row in lines) + "\n"
    sel_path = RESULTS / "frozen_test_selection.tsv"
    sel_path.write_text(tsv_text, encoding="utf-8")
    sel_sha = hashlib.sha256(tsv_text.encode("utf-8")).hexdigest()
    (RESULTS / "frozen_test_selection.tsv.sha256").write_text(
        sel_sha + "  frozen_test_selection.tsv\n", encoding="utf-8")

    # test split identity stats
    test = splits["test"]
    print("PREPARE_OK n_selected=%d seed=%d" % (len(frames), SELECT_SEED))
    print("  test_indices=%d unique=%s disjoint_train=%s disjoint_val=%s" %
          (len(test["idx"]), len(np.unique(test["idx"])) == len(test["idx"]),
           not (set(test["idx"].tolist()) & set(splits['train']['idx'].tolist())),
           not (set(test["idx"].tolist()) & set(splits['validation']['idx'].tolist()))))
    print("  selection_sha=%s" % sel_sha)
    print("  per_stratum_min=%d (all strata >= 5 test frames)" % PER_CLASS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
