#!/usr/bin/env python
"""M29 Phase D.3 Step 2 — build the dynamic-range-aware 384 calibration set.

Per the user's D.3 instruction:
  * still 24 classes x 16 samples = 384;
  * still ONLY the train split (never test) -- NOTE: the prior 384/624 sets used
    the VALIDATION split; D.3 switches to TRAIN (train is disjoint from the
    validation eval domain, eliminating any calibration<->eval overlap);
  * fixed NEW seed + deterministic selection rule;
  * per-class stratification across SNR (low/mid/high) AND amplitude
    (RMS quantiles, peak_abs, crest factor);
  * AM-SSB-WC / AM-SSB-SC MUST cover the median / 75th / 90th / 95th / high-tail
    regions of their amplitude distribution;
  * NOT "max-amplitude samples only", and NOT sample-by-sample cherry-picking
    via validation results;
  * save OLD-384 vs NEW-384 per-class / SNR / RMS / peak / crest coverage
    comparison plus all SHAs.

Selection rule (deterministic, seeded):
  1. For each class c, draw a seeded 8192-sample subset of its TRAIN rows.
  2. Compute per-sample RMS / peak_abs / crest_factor.
  3. Sort by RMS and cut 5 amplitude bins at the p50 / p75 / p90 / p95 quantiles.
  4. Allocate 16 samples across bins as [4, 3, 3, 3, 3] (body-weighted, NOT
     max-only; the high-tail bin (>=p95) gets 3).
  5. Within each bin, sort members by SNR ascending and pick k samples at
     evenly-spaced SNR-quantile positions -> low/mid/high SNR covered per bin.

READ-ONLY: no test access, no board, no model change.  Writes a FRESH dir
work/calibration_384_dra/ (never touches work/calibration_384/).
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

SEED = 20281010            # NEW fixed seed (old 384 used 2028)
PER_CLASS = 16
SUBSAMPLE = 8192           # per-class amplitude-stat estimation subset size
BIN_ALLOC = [4, 3, 3, 3, 3]   # 5 amplitude bins: [<p50, p50-75, p75-90, p90-95, >=p95]
BIN_NAMES = ["<p50", "p50-75", "p75-90", "p90-95", ">=p95"]

CAL_DIR = os.path.join(ROOT, "work", "calibration_384_dra")
CAL_DATA_DIR = os.path.join(CAL_DIR, "cal_data")
FORWARD_LIST = os.path.join(CAL_DIR, "forward_list.txt")
MANIFEST = os.path.join(CAL_DIR, "calibration_manifest.json")
MANIFEST_SHA = os.path.join(CAL_DIR, "calibration_manifest.sha256")
COMPARE = os.path.join(CAL_DIR, "calibration_coverage_compare.json")
OLD_MANIFEST = os.path.join(ROOT, "work", "calibration_384", "calibration_manifest.json")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snr_band(snr: float) -> str:
    # matches the project's 26-stratum band convention:
    #   low  = -20 .. -4 dB ; mid = -2 .. +14 dB ; high = +16 .. +30 dB
    if snr <= -4.0:
        return "low"
    if snr <= 14.0:
        return "mid"
    return "high"


def amplitude_stats(planar: np.ndarray) -> tuple[float, float, float]:
    p64 = planar.astype(np.float64)
    rms = float(np.sqrt(np.mean(p64 ** 2)))
    peak = float(np.abs(planar).max())
    crest = peak / rms if rms > 0 else 0.0
    return rms, peak, crest


def read_planar(X, source_index: int) -> np.ndarray:
    raw = np.asarray(X[source_index], dtype=np.float32)
    assert raw.shape == (1024, 2), raw.shape
    return np.ascontiguousarray(raw.T)  # [2,1024] C-order I-then-Q


def cov_summary(snrs, rms, peaks, crests):
    return {
        "n": int(len(rms)),
        "snr_min": float(min(snrs)), "snr_max": float(max(snrs)),
        "snr_band": {"low": int(sum(1 for s in snrs if snr_band(s) == "low")),
                     "mid": int(sum(1 for s in snrs if snr_band(s) == "mid")),
                     "high": int(sum(1 for s in snrs if snr_band(s) == "high"))},
        "rms_min": float(min(rms)), "rms_median": float(np.median(rms)), "rms_max": float(max(rms)),
        "peak_min": float(min(peaks)), "peak_median": float(np.median(peaks)), "peak_max": float(max(peaks)),
        "crest_min": float(min(crests)), "crest_median": float(np.median(crests)), "crest_max": float(max(crests)),
    }


def main() -> int:
    print("== M29 Phase D.3 Step 2: dynamic-range-aware 384 calibration ==")

    # ---- gate 1: HDF5 identity ----
    print("[1/7] hashing HDF5 (21.4 GiB, ~30-60 s) ...")
    hdf5_sha = sha256_file(HDF5_PATH)
    if hdf5_sha != EXPECTED_HDF5_SHA:
        print(f"  FAIL hdf5_sha256 = {hdf5_sha}")
        return 1
    print(f"  [OK] hdf5_sha256 = {hdf5_sha}")

    # ---- gate 2: index identity ----
    with open(INDEX_PATH, "rb") as f:
        index_sha = sha256_bytes(f.read())
    if index_sha != EXPECTED_INDEX_SHA:
        print(f"  FAIL index_sha256 = {index_sha}")
        return 1
    print(f"[2/7] [OK] index_sha256 = {index_sha}")

    # ---- gate 3: load ONLY train arrays (test_* never opened) ----
    with np.load(INDEX_PATH, allow_pickle=False) as idx:
        train_indices = idx["train_indices"].astype(np.int64, copy=True)
        train_labels = idx["train_labels"].astype(np.int64, copy=True)
        train_snrs = idx["train_snrs"].astype(np.float32, copy=True)
    n = len(train_indices)
    assert n == len(train_labels) == len(train_snrs)
    classes = np.unique(train_labels)
    snr_values = sorted(set(float(s) for s in train_snrs.tolist()))
    if len(classes) != 24 or set(classes.tolist()) != set(range(24)):
        return 1
    if len(snr_values) != 26:
        return 1
    print(f"[3/7] train split: {n} samples, 24 classes, {len(snr_values)} SNR strata "
          f"(test_* never read)")

    rows: list[dict] = []
    coverage_new = []
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for label in range(24):
            pos = np.flatnonzero(train_labels == label)
            rng = np.random.default_rng(SEED + label)
            if len(pos) > SUBSAMPLE:
                sub_pos = np.sort(rng.choice(pos, size=SUBSAMPLE, replace=False))
            else:
                sub_pos = np.sort(pos)
            src = train_indices[sub_pos].astype(np.int64)
            sub_snr = train_snrs[sub_pos].astype(np.float64)

            rms_l, peak_l, crest_l = [], [], []
            for si in src:
                p = read_planar(X, int(si))
                r, pk, c = amplitude_stats(p)
                rms_l.append(r); peak_l.append(pk); crest_l.append(c)
            rms_a = np.asarray(rms_l); peak_a = np.asarray(peak_l); crest_a = np.asarray(crest_l)

            # 5 amplitude bins by RMS quantiles
            q50, q75, q90, q95 = (float(np.quantile(rms_a, q)) for q in (0.50, 0.75, 0.90, 0.95))
            bin_id = np.zeros(len(rms_a), dtype=int)
            bin_id[rms_a >= q50] = 1
            bin_id[rms_a >= q75] = 2
            bin_id[rms_a >= q90] = 3
            bin_id[rms_a >= q95] = 4

            chosen = []  # (position_in_subsample)
            for b in range(5):
                k = BIN_ALLOC[b]
                mem = np.flatnonzero(bin_id == b)
                if len(mem) == 0:
                    # fallback: nearest bin with members
                    for d in range(1, 5):
                        if b - d >= 0 and np.any(bin_id == b - d):
                            mem = np.flatnonzero(bin_id == b - d); break
                        if b + d < 5 and np.any(bin_id == b + d):
                            mem = np.flatnonzero(bin_id == b + d); break
                order = mem[np.argsort(sub_snr[mem])]
                if len(order) <= k:
                    chosen.extend(int(o) for o in order)
                else:
                    idxs = np.round(np.linspace(0, len(order) - 1, k)).astype(int)
                    chosen.extend(int(order[i]) for i in idxs)
            assert len(chosen) == PER_CLASS, (label, len(chosen))

            for o in chosen:
                si = int(src[o])
                p = read_planar(X, si)
                r, pk, c = amplitude_stats(p)
                rows.append({
                    "source_index": si,
                    "label": int(label),
                    "snr_db": float(sub_snr[o]),
                    "rms": r, "peak_abs": pk, "crest_factor": c,
                    "amp_bin": BIN_NAMES[int(bin_id[o])],
                })
            cov = cov_summary([sub_snr[o] for o in chosen],
                              [rms_a[o] for o in chosen],
                              [peak_a[o] for o in chosen],
                              [crest_a[o] for o in chosen])
            cov["class"] = LABEL_ORDER_24[label]; cov["label"] = int(label)
            coverage_new.append(cov)
            print(f"  class {label:2d} {LABEL_ORDER_24[label]:12s} rms q50={q50:.3f} "
                  f"q75={q75:.3f} q90={q90:.3f} q95={q95:.3f} | sel rms "
                  f"[{cov['rms_min']:.3f},{cov['rms_median']:.3f},{cov['rms_max']:.3f}]")

    assert len(rows) == 384, len(rows)

    # ---- write .bin files ----
    os.makedirs(CAL_DATA_DIR, exist_ok=True)
    manifest_rows = []
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for i, row in enumerate(rows):
            planar = read_planar(X, row["source_index"])
            blob = planar.tobytes()
            iq_file = f"iq_{i}.bin"
            with open(os.path.join(CAL_DATA_DIR, iq_file), "wb") as out:
                out.write(blob)
            manifest_rows.append({
                "index": i,
                "class": LABEL_ORDER_24[row["label"]],
                "label": row["label"],
                "snr_db": row["snr_db"],
                "rms": row["rms"], "peak_abs": row["peak_abs"],
                "crest_factor": row["crest_factor"], "amp_bin": row["amp_bin"],
                "source_index": row["source_index"],
                "iq_file": iq_file,
                "sha256": sha256_bytes(blob),
            })

    with open(FORWARD_LIST, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(f"iq_{i}.bin" for i in range(384)) + "\n")
    with open(FORWARD_LIST, "rb") as f:
        forward_list_sha = sha256_bytes(f.read())

    # ---- old-384 coverage (recompute amplitude from old manifest source indices) ----
    with open(OLD_MANIFEST, "r", encoding="utf-8") as f:
        old = json.load(f)
    old_rows = old["rows"]
    coverage_old = []
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for label in range(24):
            rs = [r for r in old_rows if r["label"] == label]
            snrs = [r["snr_db"] for r in rs]
            rms_l, peak_l, crest_l = [], [], []
            for r in rs:
                p = read_planar(X, r["source_index"])
                rr, pk, c = amplitude_stats(p)
                rms_l.append(rr); peak_l.append(pk); crest_l.append(c)
            cov = cov_summary(snrs, rms_l, peak_l, crest_l)
            cov["class"] = LABEL_ORDER_24[label]; cov["label"] = int(label)
            coverage_old.append(cov)

    # ---- AM classes coverage proof ----
    for label in (17, 18):
        rs = [r for r in manifest_rows if r["label"] == label]
        bins = {}
        for r in rs:
            bins.setdefault(r["amp_bin"], 0)
            bins[r["amp_bin"]] += 1
        print(f"  AM {LABEL_ORDER_24[label]:12s} amp-bin coverage: "
              + " ".join(f"{b}:{bins.get(b,0)}" for b in BIN_NAMES))

    manifest = {
        "phase": "M29-Phase-D3-Step2-dynamic-range-aware-384-calibration",
        "seed": SEED,
        "split": "radioml2018_train",
        "split_note": "D.3 switches to TRAIN split (prior 384/624 used validation); "
                      "train is disjoint from the validation eval domain (no overlap)",
        "num_samples": 384, "per_class": PER_CLASS,
        "subsample_for_amplitude_quantiles": SUBSAMPLE,
        "amplitude_bins": BIN_NAMES, "bin_allocation": BIN_ALLOC,
        "amplitude_metric": "RMS (primary); peak_abs & crest_factor reported as coverage",
        "selection_rule": "5 RMS-quantile bins (p50/p75/p90/p95) x SNR-quantile spread "
                          "within each bin; body-weighted [4,3,3,3,3]; seeded deterministic; "
                          "never max-only, never validation cherry-pick",
        "num_classes": 24, "num_snr_strata": len(snr_values),
        "label_order": list(LABEL_ORDER_24),
        "snr_values": snr_values,
        "input_shape": [1, 2, 1024], "input_dtype": "float32",
        "input_layout": "planar_iq_real_imag_no_rescale",
        "bytes_per_sample": 8192,
        "byte_layout": "C-order [2,1024]: 1024 I then 1024 Q",
        "hdf5_sha256": hdf5_sha, "index_sha256": index_sha,
        "forward_list": FORWARD_LIST, "forward_list_sha256": forward_list_sha,
        "test_split_touched": False,
        "coverage_new": coverage_new,
        "coverage_old_384": coverage_old,
        "rows": manifest_rows,
    }
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    manifest_sha = sha256_file(MANIFEST)
    with open(MANIFEST_SHA, "w", encoding="utf-8") as f:
        f.write(f"{manifest_sha}  {os.path.basename(MANIFEST)}\n")

    # ---- comparison JSON ----
    compare = {
        "phase": "M29-Phase-D3-Step2-calibration-coverage-compare",
        "old_384": {"seed": old["seed"], "split": old.get("split", "validation"),
                    "per_class_coverage": coverage_old},
        "new_384": {"seed": SEED, "split": "train", "per_class_coverage": coverage_new},
    }
    with open(COMPARE, "w", encoding="utf-8") as f:
        json.dump(compare, f, indent=2)

    print(f"[6/7] forward_list.txt SHA256 = {forward_list_sha}")
    print(f"      calibration_manifest.json SHA256 = {manifest_sha}")
    print(f"      coverage compare written -> {COMPARE}")
    print("== M29 Phase D.3 Step 2 dynamic-range-aware 384 calibration PASS ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
