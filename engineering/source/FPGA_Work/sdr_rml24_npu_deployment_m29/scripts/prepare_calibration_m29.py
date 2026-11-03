#!/usr/bin/env python
"""M29 Phase C1 — validation-only INT8 calibration data for iCraft (NOT test).

Generates the iCraft quantize forward data from the REAL RadioML2018 validation
split, never the test split.  Scheme mirrors the 12-class deployment
(`model_12class/calibration/`): one sample per (class, SNR) stratum.

  * 24 classes x 26 SNR strata = 624 samples (validation split has 819 samples
    per stratum, so 1 per stratum is a small, well-covered representative draw).
  * Each sample is the raw planar I/Q [2,1024] fp32 — 8192 bytes, C-order
    (1024 I values then 1024 Q values), byte-identical to the model input.

Writes:
  work/calibration/cal_data/iq_0.bin .. iq_623.bin
  work/calibration/forward_list.txt            (single column iq_N.bin)
  work/calibration/calibration_manifest.json
  artifacts/m29_calibration_manifest.json      (copy for the audit trail)

Fail-closed gates (exit non-zero on mismatch):
  1. HDF5 SHA256 == e3dd0bef... (full 21.4 GiB hash)
  2. split-index SHA256 == 9a035841... (rml24_split_indices.npz)
  3. ONLY validation_* arrays are read; test_* arrays are never touched.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import h5py  # noqa: E402
import numpy as np  # noqa: E402

ROOT = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29"
V11 = r"F:\FPGA_Work\sdr_amr_rml24_ood_v1_1"
HDF5_PATH = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"
INDEX_PATH = os.path.join(V11, "data", "radioml2018", "rml24_split_indices.npz")

EXPECTED_HDF5_SHA = "e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38"
EXPECTED_INDEX_SHA = "9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335"

LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)

SEED = 2027
PER_STRATUM = 1

CAL_DIR = os.path.join(ROOT, "work", "calibration")
CAL_DATA_DIR = os.path.join(CAL_DIR, "cal_data")
FORWARD_LIST = os.path.join(CAL_DIR, "forward_list.txt")
MANIFEST = os.path.join(CAL_DIR, "calibration_manifest.json")
ARTIFACT_MANIFEST = os.path.join(ROOT, "artifacts", "m29_calibration_manifest.json")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    print("== M29 Phase C1: validation-only INT8 calibration ==")

    # ---- gate 1: HDF5 identity (full hash, authoritative) ----
    print(f"[1/4] hashing HDF5 {HDF5_PATH} (21.4 GiB, ~30-60 s) ...")
    hdf5_sha = sha256_file(HDF5_PATH)
    ok = hdf5_sha == EXPECTED_HDF5_SHA
    print(f"  [{'OK ' if ok else 'FAIL'}] hdf5_sha256 = {hdf5_sha}")
    if not ok:
        print(f"  expected {EXPECTED_HDF5_SHA}")
        return 1

    # ---- gate 2: split-index identity ----
    with open(INDEX_PATH, "rb") as f:
        index_sha = sha256_bytes(f.read())
    ok = index_sha == EXPECTED_INDEX_SHA
    print(f"[2/4] [{'OK ' if ok else 'FAIL'}] index_sha256 = {index_sha}")
    if not ok:
        print(f"  expected {EXPECTED_INDEX_SHA}")
        return 1

    # ---- load ONLY validation arrays (test_* never opened) ----
    with np.load(INDEX_PATH, allow_pickle=False) as idx:
        assert "test_indices" in idx, "index missing test arrays (unexpected)"
        val_indices = idx["validation_indices"].astype(np.int64, copy=True)
        val_labels = idx["validation_labels"].astype(np.int64, copy=True)
        val_snrs = idx["validation_snrs"].astype(np.float32, copy=True)
    n = len(val_indices)
    assert n == len(val_labels) == len(val_snrs)
    print(f"[3/4] validation split: {n} samples, {len(np.unique(val_indices))} unique rows")

    classes = np.unique(val_labels)
    snr_values = sorted(set(float(s) for s in val_snrs.tolist()))
    if len(classes) != 24 or set(classes.tolist()) != set(range(24)):
        print(f"  FAIL: expected 24 classes 0..23, got {sorted(classes.tolist())}")
        return 1
    print(f"  24 classes, {len(snr_values)} SNR strata {snr_values}")

    # ---- deterministic stratified draw: 1 per (label, snr) stratum ----
    rng = np.random.default_rng(SEED)
    rows: list[dict] = []
    strata_meta: list[dict] = []
    for label in range(24):
        for snr in snr_values:
            positions = np.flatnonzero((val_labels == label) & (val_snrs == snr))
            if len(positions) < PER_STRATUM:
                print(f"  FAIL: (label={label}, snr={snr}) has only {len(positions)} samples")
                return 1
            order = positions.copy()
            rng.shuffle(order)
            chosen = order[:PER_STRATUM]
            for pos in chosen:
                rows.append({
                    "source_index": int(val_indices[pos]),
                    "label": int(label),
                    "snr_db": float(snr),
                })
            strata_meta.append({"label": int(label), "snr_db": float(snr),
                                "stratum_size": int(len(positions))})

    num_samples = len(rows)
    print(f"[4/4] selected {num_samples} calibration samples "
          f"(24 classes x {len(snr_values)} SNR x {PER_STRATUM})")

    # ---- write .bin files (planar [2,1024] fp32, C-order I-then-Q) ----
    os.makedirs(CAL_DATA_DIR, exist_ok=True)
    manifest_rows = []
    class_counts = [0] * 24
    snr_counts = {s: 0 for s in snr_values}
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for i, row in enumerate(rows):
            raw = np.asarray(X[row["source_index"]], dtype=np.float32)
            if raw.shape != (1024, 2):
                print(f"  FAIL: unexpected sample shape {raw.shape} at row {row['source_index']}")
                return 1
            planar = np.ascontiguousarray(raw.T)  # [2, 1024], C-order
            if planar.nbytes != 8192:
                print(f"  FAIL: sample bytes {planar.nbytes} != 8192")
                return 1
            iq_file = f"iq_{i}.bin"
            with open(os.path.join(CAL_DATA_DIR, iq_file), "wb") as out:
                out.write(planar.tobytes())
            class_counts[row["label"]] += 1
            snr_counts[row["snr_db"]] += 1
            manifest_rows.append({
                "index": i,
                "class": LABEL_ORDER_24[row["label"]],
                "label": row["label"],
                "snr_db": row["snr_db"],
                "source_index": row["source_index"],
                "iq_file": iq_file,
            })

    # ---- forward_list.txt (single column) ----
    with open(FORWARD_LIST, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(f"iq_{i}.bin" for i in range(num_samples)) + "\n")
    with open(FORWARD_LIST, "rb") as f:
        forward_list_sha = sha256_bytes(f.read())

    manifest = {
        "phase": "M29-Phase-C1-validation-only-calibration",
        "seed": SEED,
        "split": "radioml2018_validation",
        "num_samples": num_samples,
        "per_stratum": PER_STRATUM,
        "num_classes": 24,
        "num_snr_strata": len(snr_values),
        "label_order": list(LABEL_ORDER_24),
        "snr_values": snr_values,
        "input_shape": [1, 2, 1024],
        "input_dtype": "float32",
        "input_layout": "planar_iq_real_imag_rms_1.0_no_rescale",
        "bytes_per_sample": 8192,
        "byte_layout": "C-order [2,1024]: 1024 I then 1024 Q",
        "hdf5_path": HDF5_PATH,
        "hdf5_sha256": hdf5_sha,
        "index_path": INDEX_PATH,
        "index_sha256": index_sha,
        "forward_list": FORWARD_LIST,
        "forward_list_sha256": forward_list_sha,
        "per_class_counts": class_counts,
        "per_snr_counts": snr_counts,
        "test_split_touched": False,
        "rows": manifest_rows,
        "strata": strata_meta,
    }
    for path in (MANIFEST, ARTIFACT_MANIFEST):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"  wrote {path}")

    # final self-check: per-class and per-snr coverage is full
    assert all(c == len(snr_values) for c in class_counts), class_counts
    assert all(c == 24 for c in snr_counts.values()), snr_counts
    print(f"  forward_list.txt SHA256 = {forward_list_sha}")
    print("== M29 Phase C1 PASS ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
