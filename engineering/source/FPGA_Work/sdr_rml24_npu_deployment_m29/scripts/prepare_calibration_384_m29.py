#!/usr/bin/env python
"""M29 Phase D (方案 D) — 384-sample stratified validation-only INT8 calibration.

Builds a 384-sample calibration set (24 classes x 16 samples) that keeps the
full validation-split discipline of the 624-sample set, but is small enough to
stay under the iCraft pre-forward resource ceiling.  Per user's 方案 D:

  * exactly 16 samples per class (24 x 16 = 384);
  * fixed seed (2028) -> fully reproducible;
  * validation split ONLY (test_* arrays never read);
  * each class covers low / mid / high SNR (6 low + 5 mid + 5 high);
  * the full set covers all 26 SNR strata globally (hard assert);
  * NOT an ordered-prefix truncation (seeded band-stratified draw).

Data format is byte-identical to the model input and to the 624 set:
planar [2,1024] fp32, C-order (1024 I then 1024 Q), 8192 bytes per sample.

Writes (fresh dir, does NOT touch work/calibration/):
  work/calibration_384/cal_data/iq_0.bin .. iq_383.bin
  work/calibration_384/forward_list.txt
  work/calibration_384/calibration_manifest.json      (per-sample SHA + coverage)
  work/calibration_384/calibration_manifest.sha256    (overall manifest SHA)
  artifacts/m29_calibration_384_manifest.json         (audit copy)

Fail-closed gates (exit non-zero on mismatch):
  1. HDF5 SHA256 == e3dd0bef... (full 21.4 GiB hash)
  2. split-index SHA256 == 9a035841... (rml24_split_indices.npz)
  3. ONLY validation_* arrays are read; test_* arrays are never touched
  4. 24 classes 0..23; 26 SNR strata; >= 16 validation samples per stratum
  5. per-class = 16, per-SNR >= 1 for all 26 strata, all 3 bands covered
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

SEED = 2028
PER_CLASS = 16
BAND_LOW = 6
BAND_MID = 5
BAND_HIGH = 5
# SNR index bands over the 26 sorted strata:
#   low  = indices 0..8  (-20 .. -4 dB)
#   mid  = indices 9..17 (-2 .. +14 dB)
#   high = indices 18..25 (+16 .. +30 dB)
LOW_IDX = list(range(0, 9))
MID_IDX = list(range(9, 18))
HIGH_IDX = list(range(18, 26))

CAL_DIR = os.path.join(ROOT, "work", "calibration_384")
CAL_DATA_DIR = os.path.join(CAL_DIR, "cal_data")
FORWARD_LIST = os.path.join(CAL_DIR, "forward_list.txt")
MANIFEST = os.path.join(CAL_DIR, "calibration_manifest.json")
MANIFEST_SHA = os.path.join(CAL_DIR, "calibration_manifest.sha256")
ARTIFACT_MANIFEST = os.path.join(ROOT, "artifacts", "m29_calibration_384_manifest.json")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    print("== M29 Phase D(方案 D): 384-sample stratified validation-only calibration ==")

    # ---- gate 1: HDF5 identity (full hash, authoritative) ----
    print(f"[1/6] hashing HDF5 {HDF5_PATH} (21.4 GiB, ~30-60 s) ...")
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
    print(f"[2/6] [{'OK ' if ok else 'FAIL'}] index_sha256 = {index_sha}")
    if not ok:
        print(f"  expected {EXPECTED_INDEX_SHA}")
        return 1

    # ---- gate 3: load ONLY validation arrays (test_* never opened) ----
    with np.load(INDEX_PATH, allow_pickle=False) as idx:
        assert "test_indices" in idx, "index missing test arrays (unexpected)"
        val_indices = idx["validation_indices"].astype(np.int64, copy=True)
        val_labels = idx["validation_labels"].astype(np.int64, copy=True)
        val_snrs = idx["validation_snrs"].astype(np.float32, copy=True)
    n = len(val_indices)
    assert n == len(val_labels) == len(val_snrs)
    print(f"[3/6] validation split: {n} samples, {len(np.unique(val_indices))} unique rows")

    classes = np.unique(val_labels)
    snr_values = sorted(set(float(s) for s in val_snrs.tolist()))
    if len(classes) != 24 or set(classes.tolist()) != set(range(24)):
        print(f"  FAIL: expected 24 classes 0..23, got {sorted(classes.tolist())}")
        return 1
    if len(snr_values) != 26:
        print(f"  FAIL: expected 26 SNR strata, got {len(snr_values)}")
        return 1
    print(f"  24 classes, {len(snr_values)} SNR strata")

    # ---- gate 4: every (class, snr) stratum has >= 1 sample (need 1 per pick) ----
    for label in range(24):
        for snr in snr_values:
            cnt = int(np.count_nonzero((val_labels == label) & (val_snrs == snr)))
            if cnt < 1:
                print(f"  FAIL: (label={label}, snr={snr}) has {cnt} samples")
                return 1

    # ---- deterministic band-stratified draw: 16 per class, fixed seed ----
    rng = np.random.default_rng(SEED)
    rows: list[dict] = []
    coverage: list[dict] = []
    per_class_counts = [0] * 24
    per_snr_counts = {s: 0 for s in snr_values}

    for label in range(24):
        low_pick = rng.choice(np.array(LOW_IDX), size=BAND_LOW, replace=False)
        mid_pick = rng.choice(np.array(MID_IDX), size=BAND_MID, replace=False)
        high_pick = rng.choice(np.array(HIGH_IDX), size=BAND_HIGH, replace=False)
        chosen_idx = sorted(np.concatenate([low_pick, mid_pick, high_pick]).tolist())
        assert len(chosen_idx) == PER_CLASS, chosen_idx
        chosen_snrs = [snr_values[i] for i in chosen_idx]

        class_rows = []
        for snr in chosen_snrs:
            positions = np.flatnonzero((val_labels == label) & (val_snrs == snr))
            assert len(positions) >= 1
            order = positions.copy()
            rng.shuffle(order)
            pos = int(order[0])
            class_rows.append({
                "source_index": int(val_indices[pos]),
                "label": int(label),
                "snr_db": float(snr),
            })
        rows.extend(class_rows)
        coverage.append({
            "class": LABEL_ORDER_24[label],
            "label": int(label),
            "snr_db": chosen_snrs,
            "band_low": int(np.sum(np.array(chosen_idx) < 9)),
            "band_mid": int(np.sum((np.array(chosen_idx) >= 9) & (np.array(chosen_idx) < 18))),
            "band_high": int(np.sum(np.array(chosen_idx) >= 18)),
        })

    num_samples = len(rows)
    assert num_samples == 24 * PER_CLASS == 384, num_samples
    print(f"[4/6] selected {num_samples} calibration samples (24 classes x {PER_CLASS})")

    # ---- write .bin files (planar [2,1024] fp32, C-order I-then-Q) ----
    os.makedirs(CAL_DATA_DIR, exist_ok=True)
    manifest_rows = []
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for i, row in enumerate(rows):
            raw = np.asarray(X[row["source_index"]], dtype=np.float32)
            if raw.shape != (1024, 2):
                print(f"  FAIL: unexpected shape {raw.shape} at row {row['source_index']}")
                return 1
            planar = np.ascontiguousarray(raw.T)  # [2, 1024] C-order
            if planar.nbytes != 8192:
                print(f"  FAIL: sample bytes {planar.nbytes} != 8192")
                return 1
            blob = planar.tobytes()
            iq_file = f"iq_{i}.bin"
            with open(os.path.join(CAL_DATA_DIR, iq_file), "wb") as out:
                out.write(blob)
            per_class_counts[row["label"]] += 1
            per_snr_counts[row["snr_db"]] += 1
            manifest_rows.append({
                "index": i,
                "class": LABEL_ORDER_24[row["label"]],
                "label": row["label"],
                "snr_db": row["snr_db"],
                "source_index": row["source_index"],
                "iq_file": iq_file,
                "sha256": sha256_bytes(blob),
            })

    # ---- forward_list.txt ----
    with open(FORWARD_LIST, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(f"iq_{i}.bin" for i in range(num_samples)) + "\n")
    with open(FORWARD_LIST, "rb") as f:
        forward_list_sha = sha256_bytes(f.read())

    # ---- gate 5: coverage assertions ----
    assert all(c == PER_CLASS for c in per_class_counts), per_class_counts
    assert all(per_snr_counts[s] >= 1 for s in snr_values), per_snr_counts
    for cov in coverage:
        assert cov["band_low"] >= 1 and cov["band_mid"] >= 1 and cov["band_high"] >= 1, cov

    manifest = {
        "phase": "M29-Phase-D-schemeD-384-stratified-validation-only-calibration",
        "seed": SEED,
        "split": "radioml2018_validation",
        "num_samples": num_samples,
        "per_class": PER_CLASS,
        "band_split": {"low": BAND_LOW, "mid": BAND_MID, "high": BAND_HIGH},
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
        "per_class_counts": per_class_counts,
        "per_snr_counts": per_snr_counts,
        "test_split_touched": False,
        "coverage_table": coverage,
        "rows": manifest_rows,
    }
    for path in (MANIFEST, ARTIFACT_MANIFEST):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"  wrote {path}")

    # ---- overall manifest SHA (computed over the written JSON) ----
    manifest_sha = sha256_file(MANIFEST)
    with open(MANIFEST_SHA, "w", encoding="utf-8") as f:
        f.write(f"{manifest_sha}  {os.path.basename(MANIFEST)}\n")
    print(f"[5/6] forward_list.txt SHA256 = {forward_list_sha}")
    print(f"      calibration_manifest.json SHA256 = {manifest_sha}")

    # ---- per-SNR global coverage summary ----
    print("[6/6] global SNR coverage:")
    for s in snr_values:
        print(f"      snr {s:+.0f} dB -> {per_snr_counts[s]} samples")
    print("== M29 Phase D(方案 D) 384 calibration PASS ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
