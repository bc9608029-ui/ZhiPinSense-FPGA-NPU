#!/usr/bin/env python3
"""build_clean24_smoke_d2.py -- fix10class24-prep1 (任务四): build the 24-class
clean-IQ Route-D2 smoke assets from clean24_formal12000.hdf5.

For each of the 24 source modulation classes, take the FIXED first k=0 sample
(source_index = class_index * 500, never confidence-picked, never swapped) and
produce the exact Route-D2 non-training artifacts:

  clean_<slug>_<sha8>.ci16        interleaved int16 LE (I,Q,...), AC-ONLY, x20
                                  interpolated to 2.56 MSPS (53760 complex =
                                  215040 bytes).
  source_<slug>.f32               [2,1024] fp32 planar [real,imag] (8192 bytes),
                                  the ORIGINAL clean2a source sample.
  recovered_tensor_<slug>.f32     [2,1024] fp32 (8192 bytes), the D2 reference
                                  (AC re-mapped + DC restored).
  selected_samples.tsv            15-col fixed-selection table (selection_rule =
                                  first_per_class_k0).
  route_d2_rf_manifest.tsv        24 columns (the load_d2_sidecar schema).
  clean24_smoke_manifest.tsv      27 columns (24 + tx_scale + frozen_raw24_pred
                                  + frozen_deployed23_pred).
  clean24_smoke_clean_baseline.tsv  6-col CLEAN digital-injection baseline.
  clean24_smoke_baseline.tsv        6-col future dual-SDR baseline.
  raw24_to_deployed23_mapping.tsv   24-row 24->23 coverage mapping.
  clean24_smoke_build_report.json   metadata + per-sample metrics (no self SHA).
  clean24_smoke_SHA256SUMS.txt       content-file SHAs (never itself).

The D2 resampling + recovery math is NEVER re-implemented here: only
analyze_route_d2_4ask.reconstruct(...) and .recovered_tensor_1024(...) are
imported (fail-closed on the authority SHA).  The label order is NEVER
hand-written: SOURCE_LABEL_ORDER_24 / DEPLOYED_LABEL_ORDER_23 / SOURCE_TO_DEPLOYED
are read directly from the frozen 24->23 contract.

Deterministic: every byte is derived from the frozen HDF5 fp32 sample; two
in-process builds must be byte-identical (SHA-equal) or the script fails closed.

Pure stdlib + numpy + h5py (no torch).  Run isolated:  python -B -I <this file>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile

# Never write .pyc into the READ-ONLY reference trees (authority + contract).
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402
import h5py  # noqa: E402

# --- D2 authority (read-only import; only these two names are used) ----------
AUTHORITY_DIR = r"F:\嵌赛\fix10clean2b_work\sdr_rml23_live_board_package_iq_rf_loopback_fix10clean2b\scripts"
AUTHORITY_PATH = os.path.join(AUTHORITY_DIR, "analyze_route_d2_4ask.py")
sys.path.insert(0, AUTHORITY_DIR)
import analyze_route_d2_4ask as A  # noqa: E402

# --- 24->23 merged contract (read-only import; no hand-written label order) --
CONTRACT_DIR = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\contracts"
CONTRACT_PATH = os.path.join(CONTRACT_DIR, "rml23_merged_contract.py")
sys.path.insert(0, CONTRACT_DIR)
from rml23_merged_contract import (  # noqa: E402
    DEPLOYED_LABEL_ORDER_23, SOURCE_LABEL_ORDER_24, SOURCE_TO_DEPLOYED,
    assert_source_order_matches, assert_23class_contract_consistent,
)

DATASET_PATH = r"F:/嵌赛/fix10clean2a_dataset/clean24_formal12000.hdf5"
PRED_TSV_PATH = r"F:/嵌赛/fix10clean2a_results/frozen_model_predictions_formal12000.tsv"
DEFAULT_OUT_DIR = r"F:/嵌赛/fix10class24_prep1_work/clean24_smoke"

# --- frozen input SHAs (recomputed 2026-10-17, cross-checked vs clean2a audit) -
EXPECTED_DATASET_SHA = "8b3efe0b11143b31972d392f5b85bc8bd3faf7973681c4d5d7da7ed9603ed81a"
EXPECTED_PRED_SHA = "dd1938fa34989fa2853a46e6d298630c7984ad4e5661dd77f9635d0fecf2ba71"
EXPECTED_CONTRACT_SHA = "31deebc03ca9c36fafb7cd69b85a60dae2bbaff5e3be7a1f7899fc1fae64a48e"
EXPECTED_AUTHORITY_SHA = "0324899eaad37de487ee2dc950c0af54eec3a753f941caba75e2de3d1f525bfa"

# --- fixed D2 parameters (== clean2b smoke) ---------------------------------
K = 2048.0
EDGE = "zero"
GUARD = 832
COMPLEX_COUNT = 53760
SAMPLE_RATE_HZ = 2560000
TARGET_RMS = 2048
SPLIT_ROLE = "holdout"
SNR_DB = "nan"
SEED_BASE = 2000000        # formal12000 seed base (HDF5 attr seed_base)
SPC = 500                  # samples per class (HDF5 attr samples_per_class)
SELECTION_RULE = "first_per_class_k0"

MANIFEST_HEADER = [
    "sample_index", "source_index", "raw24_class", "deployed23_class",
    "modulation", "snr_db", "split_role", "global_K", "original_dc_i",
    "original_dc_q", "ac_rms", "rec_scale", "complex_count", "sample_rate",
    "tx_rms", "tx_peak", "clip_count", "edge_policy", "guard",
    "original_sha256", "quantized_sha256", "recovered_tensor_sha256",
    "quantized_file", "recovered_tensor_file",
]
EXTRA_HEADER = ["tx_scale", "frozen_raw24_pred", "frozen_deployed23_pred"]

CLEAN_BASELINE_HEADER = ["source_index", "file_name", "sha256", "deployed_class",
                         "split_role", "frozen_baseline_pred"]
DUAL_SDR_BASELINE_HEADER = ["source_index", "original_sha256", "deployed_class",
                            "modulation", "split_role", "frozen_baseline_pred"]

SELECTED_HEADER = [
    "class_index", "source_index", "seed", "raw24_label", "deployed23_index",
    "deployed23_label", "selection_rule", "raw24_pred", "deployed23_pred",
    "top1_logit", "top2_logit", "margin", "correct_raw24", "correct_deployed23",
]

MAPPING_HEADER = ["class_index", "raw24_label", "deployed23_index", "deployed23_label"]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(label: str) -> str:
    """Stable, collision-free filename slug: lowercase, '-' -> '_'."""
    return label.lower().replace("-", "_")


def fixed_samples() -> list[dict]:
    """The 24 FIXED samples: source_index = class_index * 500, k=0.

    Labels are derived ONLY from the frozen contract (never hand-written).
    """
    samples = []
    for ci in range(len(SOURCE_LABEL_ORDER_24)):
        samples.append({
            "class_index": ci,
            "source_index": ci * SPC,
            "seed": SEED_BASE + ci * SPC,      # k == 0
            "raw24_label": SOURCE_LABEL_ORDER_24[ci],
            "deployed23_class": int(SOURCE_TO_DEPLOYED[ci]),
        })
    # fail-closed: slug uniqueness (no /, space, case collisions)
    slugs = [slug(s["raw24_label"]) for s in samples]
    if len(set(slugs)) != len(slugs):
        raise SystemExit("slug collision among the 24 class labels")
    return samples


def load_predictions(tsv_path: str) -> dict[int, dict]:
    """Parse the 10-column frozen predictions TSV into sample_id -> row dict.

    Fail-closed: missing/duplicate sample_id, malformed row, wrong header all
    raise (never a positional lookup, never a silent fallback).
    """
    preds: dict[int, dict] = {}
    with open(tsv_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    if not lines:
        raise SystemExit("predictions TSV is empty: %s" % tsv_path)
    header = lines[0].split("\t")
    assert header == ["sample_id", "raw24_label", "deployed23_label",
                      "raw24_pred", "deployed23_pred", "top1_logit",
                      "top2_logit", "margin", "correct_raw24",
                      "correct_deployed23"], \
        "unexpected predictions TSV header: %r" % header
    for line in lines[1:]:
        if not line:
            continue
        p = line.split("\t")
        if len(p) < 10:
            raise SystemExit("malformed predictions row (want 10 cols): %r" % line)
        sid = int(p[0])
        if sid in preds:
            raise SystemExit("duplicate sample_id %d in predictions TSV" % sid)
        preds[sid] = {
            "raw24_label": p[1], "deployed23_label": p[2],
            "raw24_pred": p[3], "deployed23_pred": p[4],
            "top1_logit": p[5], "top2_logit": p[6], "margin": p[7],
            "correct_raw24": int(p[8]), "correct_deployed23": int(p[9]),
        }
    return preds


def verify_input_shas() -> None:
    for path, want, name in (
            (DATASET_PATH, EXPECTED_DATASET_SHA, "dataset"),
            (PRED_TSV_PATH, EXPECTED_PRED_SHA, "predictions TSV"),
            (CONTRACT_PATH, EXPECTED_CONTRACT_SHA, "24->23 contract"),
            (AUTHORITY_PATH, EXPECTED_AUTHORITY_SHA, "D2 authority")):
        got = sha256_file(path)
        if got != want:
            raise SystemExit("%s SHA mismatch: got %s, expected %s"
                             % (name, got, want))


def read_hdf5() -> tuple[np.ndarray, np.ndarray, np.ndarray, list]:
    """Read the clean24 formal12000 HDF5 and fail-closed on structure/labels."""
    with h5py.File(DATASET_PATH, "r") as f:
        X = f["X"][:]        # [N, 1024, 2] fp32
        Y = np.asarray(f["Y"]).astype(np.int64)
        seeds = np.asarray(f["seeds"]).astype(np.int64)
        order = json.loads(f.attrs["label_order"])
        seed_base = int(f.attrs["seed_base"])
        spc = int(f.attrs["samples_per_class"])
    if X.shape != (12000, 1024, 2) or X.dtype != np.float32:
        raise SystemExit("unexpected X shape/dtype: %r %r" % (X.shape, X.dtype))
    if Y.shape != (12000,) or seeds.shape != (12000,):
        raise SystemExit("unexpected Y/seeds shape: %r %r" % (Y.shape, seeds.shape))
    if list(order) != list(SOURCE_LABEL_ORDER_24):
        raise SystemExit("HDF5 label_order mismatch vs frozen 24-class order")
    if seed_base != SEED_BASE or spc != SPC:
        raise SystemExit("HDF5 seed_base/samples_per_class mismatch: %d/%d"
                         % (seed_base, spc))
    return X, Y, seeds, order


def build_artifacts(out_dir: str) -> tuple[dict, dict]:
    """Write the deterministic artifacts (72 binaries + 7 TSVs) into out_dir.

    Returns (sha_map {relpath -> sha256}, report_meta).  Does NOT write the
    build report or the SHA sidecar (finalised in main()).
    """
    os.makedirs(out_dir, exist_ok=True)
    verify_input_shas()
    assert_source_order_matches(SOURCE_LABEL_ORDER_24)
    assert_23class_contract_consistent()

    X, Y, seeds, _order = read_hdf5()
    preds = load_predictions(PRED_TSV_PATH)
    samples = fixed_samples()

    manifest_rows_24: list[list[str]] = []
    manifest_rows_27: list[list[str]] = []
    selected_rows: list[list[str]] = []
    clean_baseline_rows: list[list[str]] = []
    dual_baseline_rows: list[list[str]] = []
    mapping_rows: list[list[str]] = []
    sha_map: dict[str, str] = {}
    per_sample: list[dict] = []

    seen_source: set[int] = set()
    raw_labels: list[str] = []
    deployed_indices: list[int] = []
    label_correct = 0

    for out_idx, s in enumerate(samples):
        row = s["source_index"]
        if row in seen_source:
            raise SystemExit("duplicate source_index %d" % row)
        seen_source.add(row)

        y = int(Y[row])
        seed = int(seeds[row])
        if y != s["class_index"]:
            raise SystemExit("row %d has Y=%d, expected class_index %d (%s)"
                             % (row, y, s["class_index"], s["raw24_label"]))
        if seed != s["seed"]:
            raise SystemExit("row %d has seed=%d, expected %d"
                             % (row, seed, s["seed"]))
        raw_labels.append(s["raw24_label"])
        deployed_indices.append(s["deployed23_class"])

        xr = X[row, :, 0].astype(np.float64)
        xi = X[row, :, 1].astype(np.float64)
        x = xr + 1j * xi                                    # 1024 complex

        # Route-D2 reconstruction (imported, never re-implemented).
        r = A.reconstruct(x, "D2", K, edge=EDGE, guard=GUARD)

        ci16 = np.ascontiguousarray(r["iq"], dtype="<i2")    # 53760 complex int16
        source_float = np.ascontiguousarray(
            np.stack([x.real, x.imag]), dtype="<f4")         # [2,1024] f32
        recovered_tensor = np.ascontiguousarray(
            A.recovered_tensor_1024(x, r["recovered"]), dtype="<f4")  # [2048] f32

        if ci16.size != 2 * COMPLEX_COUNT:
            raise SystemExit("ci16 size %d != %d" % (ci16.size, 2 * COMPLEX_COUNT))
        if ci16.dtype != np.dtype("<i2") or not ci16.flags.c_contiguous:
            raise SystemExit("ci16 not contiguous little-endian int16")
        if source_float.dtype != np.dtype("<f4") or not source_float.flags.c_contiguous:
            raise SystemExit("source_float not contiguous little-endian f32")
        if recovered_tensor.dtype != np.dtype("<f4") or not recovered_tensor.flags.c_contiguous:
            raise SystemExit("recovered_tensor not contiguous little-endian f32")
        if recovered_tensor.size != 2 * 1024:
            raise SystemExit("recovered_tensor size %d != 2048" % recovered_tensor.size)

        d2_ci16_sha256 = sha256_bytes(ci16.tobytes())
        source_float_sha256 = sha256_bytes(source_float.tobytes())
        recovered_tensor_sha256 = sha256_bytes(recovered_tensor.tobytes())

        if source_float_sha256 == d2_ci16_sha256:
            raise SystemExit("source_float_sha256 == d2_ci16_sha256 (must differ)")

        tag = slug(s["raw24_label"])
        qname = "clean_%s_%s.ci16" % (tag, d2_ci16_sha256[:8])
        rname = "recovered_tensor_%s.f32" % tag
        sname = "source_%s.f32" % tag
        ci16.tofile(os.path.join(out_dir, qname))
        recovered_tensor.tofile(os.path.join(out_dir, rname))
        source_float.tofile(os.path.join(out_dir, sname))

        for name, want in ((qname, d2_ci16_sha256), (rname, recovered_tensor_sha256),
                           (sname, source_float_sha256)):
            got = sha256_file(os.path.join(out_dir, name))
            if got != want:
                raise SystemExit("on-disk SHA mismatch for %s" % name)
            sha_map[name] = got

        native_rms = float(r["quant_rms_counts"])
        # tx_peak read DIRECTLY from the ci16 bytes (never a non-existent field).
        tx_peak = float(np.max(np.abs(ci16.astype(np.float64))))
        tx_scale = TARGET_RMS / native_rms
        clip_count = int(r["clip_count"])

        if clip_count != 0:
            raise SystemExit("clip_count=%d != 0 for clean %s (no clipping allowed)"
                             % (clip_count, tag))
        if not (native_rms > 0.0) or not np.isfinite(tx_scale) or tx_scale <= 0.0:
            raise SystemExit("bad native_rms/tx_scale for %s" % tag)

        # Frozen predictions from the clean2a Phase-5 TSV (exact sample_id key).
        pr = preds.get(s["source_index"])
        if pr is None:
            raise SystemExit("sample_id %d missing from predictions TSV" % s["source_index"])
        expected_dep23_label = DEPLOYED_LABEL_ORDER_23[s["deployed23_class"]]
        if pr["raw24_label"] != s["raw24_label"]:
            raise SystemExit("sample_id %d raw24_label %r != %r"
                             % (s["source_index"], pr["raw24_label"], s["raw24_label"]))
        if pr["deployed23_label"] != expected_dep23_label:
            raise SystemExit("sample_id %d deployed23_label %r != %r"
                             % (s["source_index"], pr["deployed23_label"], expected_dep23_label))
        frozen_raw24_pred = SOURCE_LABEL_ORDER_24.index(pr["raw24_pred"])
        frozen_deployed23_pred = DEPLOYED_LABEL_ORDER_23.index(pr["deployed23_pred"])
        if pr["correct_raw24"] != 1 or pr["correct_deployed23"] != 1:
            raise SystemExit("sample_id %d not label-correct in predictions TSV"
                             % s["source_index"])
        if frozen_raw24_pred != s["class_index"]:
            raise SystemExit("frozen_raw24_pred %d != class_index %d for %s"
                             % (frozen_raw24_pred, s["class_index"], tag))
        if frozen_deployed23_pred != s["deployed23_class"]:
            raise SystemExit("frozen_deployed23_pred %d != deployed23_class %d for %s"
                             % (frozen_deployed23_pred, s["deployed23_class"], tag))
        label_correct += 1

        cols24 = [
            str(out_idx), str(s["source_index"]), str(s["class_index"]),
            str(s["deployed23_class"]), s["raw24_label"], SNR_DB, SPLIT_ROLE,
            "%.0f" % K, "%.9g" % float(r["dc_i"]), "%.9g" % float(r["dc_q"]),
            "%.9g" % float(r["ac_rms"]), "%.9g" % float(r["rec_scale"]),
            str(COMPLEX_COUNT), str(SAMPLE_RATE_HZ), "%.6f" % native_rms,
            "%.6f" % tx_peak, str(clip_count), EDGE, str(GUARD),
            source_float_sha256, d2_ci16_sha256, recovered_tensor_sha256,
            qname, rname,
        ]
        manifest_rows_24.append(cols24)
        manifest_rows_27.append(cols24 + [
            "%.12g" % tx_scale, str(frozen_raw24_pred), str(frozen_deployed23_pred),
        ])
        selected_rows.append([
            str(s["class_index"]), str(s["source_index"]), str(seed),
            s["raw24_label"], str(s["deployed23_class"]), expected_dep23_label,
            SELECTION_RULE, pr["raw24_pred"], pr["deployed23_pred"],
            "%.6f" % float(pr["top1_logit"]), "%.6f" % float(pr["top2_logit"]),
            "%.6f" % float(pr["margin"]),
            str(pr["correct_raw24"]), str(pr["correct_deployed23"]),
        ])
        clean_baseline_rows.append([
            str(s["source_index"]), qname, d2_ci16_sha256,
            str(s["deployed23_class"]), SPLIT_ROLE, str(frozen_deployed23_pred),
        ])
        dual_baseline_rows.append([
            str(s["source_index"]), source_float_sha256, str(s["deployed23_class"]),
            s["raw24_label"], SPLIT_ROLE, str(frozen_deployed23_pred),
        ])
        mapping_rows.append([
            str(s["class_index"]), s["raw24_label"],
            str(s["deployed23_class"]), expected_dep23_label,
        ])
        per_sample.append({
            "class_index": s["class_index"], "source_index": s["source_index"],
            "seed": seed, "raw24_label": s["raw24_label"],
            "deployed23_index": s["deployed23_class"],
            "deployed23_label": expected_dep23_label,
            "frozen_raw24_pred": frozen_raw24_pred,
            "frozen_deployed23_pred": frozen_deployed23_pred,
            "top1_logit": float(pr["top1_logit"]),
            "top2_logit": float(pr["top2_logit"]),
            "margin": float(pr["margin"]),
            "source_sha256": source_float_sha256,
            "quantized_sha256": d2_ci16_sha256,
            "recovered_tensor_sha256": recovered_tensor_sha256,
            "dc_i": float(r["dc_i"]), "dc_q": float(r["dc_q"]),
            "ac_rms": float(r["ac_rms"]), "rec_scale": float(r["rec_scale"]),
            "native_rms": native_rms, "tx_peak": tx_peak,
            "tx_scale": tx_scale, "clip_count": clip_count,
        })

    # --- 24->23 coverage gate ------------------------------------------------
    n_samples = len(samples)
    raw24_classes = len(set(raw_labels))
    deployed23_classes = len(set(deployed_indices))
    amssb_merged = DEPLOYED_LABEL_ORDER_23.index("AM-SSB")
    amssb_count = sum(1 for d in deployed_indices if d == amssb_merged)
    if sorted(raw_labels) != sorted(SOURCE_LABEL_ORDER_24):
        raise SystemExit("raw24 labels do not exactly cover SOURCE_LABEL_ORDER_24")
    if sorted(set(deployed_indices)) != list(range(23)):
        raise SystemExit("deployed23 indices do not exactly cover 0..22")
    if amssb_count != 2:
        raise SystemExit("AM-SSB deployed class must absorb exactly 2 source samples, got %d"
                         % amssb_count)
    for d in range(23):
        c = sum(1 for x in deployed_indices if x == d)
        if d == amssb_merged and c != 2:
            raise SystemExit("AM-SSB deployed slot count %d != 2" % c)
        if d != amssb_merged and c != 1:
            raise SystemExit("deployed slot %d count %d != 1" % (d, c))

    if label_correct != n_samples:
        raise SystemExit("label_correct %d/%d != %d/%d"
                         % (label_correct, n_samples, n_samples, n_samples))

    def _write_tsv(name: str, header: list[str], rows: list[list[str]]) -> None:
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\t".join(header) + "\n")
            for rr in rows:
                fh.write("\t".join(rr) + "\n")
        sha_map[name] = sha256_file(path)

    _write_tsv("route_d2_rf_manifest.tsv", MANIFEST_HEADER, manifest_rows_24)
    _write_tsv("clean24_smoke_manifest.tsv", MANIFEST_HEADER + EXTRA_HEADER,
               manifest_rows_27)
    _write_tsv("selected_samples.tsv", SELECTED_HEADER, selected_rows)
    _write_tsv("clean24_smoke_clean_baseline.tsv", CLEAN_BASELINE_HEADER,
               clean_baseline_rows)
    _write_tsv("clean24_smoke_baseline.tsv", DUAL_SDR_BASELINE_HEADER,
               dual_baseline_rows)
    _write_tsv("raw24_to_deployed23_mapping.tsv", MAPPING_HEADER, mapping_rows)

    report_meta = {
        "n_samples": n_samples,
        "raw24_class_coverage": "%d/%d" % (raw24_classes, 24),
        "deployed23_class_coverage": "%d/%d" % (deployed23_classes, 23),
        "clip_count_zero": "%d/%d" % (sum(1 for p in per_sample if p["clip_count"] == 0),
                                      n_samples),
        "label_correct": "%d/%d" % (label_correct, n_samples),
        "amssb_merged_count": amssb_count,
        "per_sample": per_sample,
    }
    return sha_map, report_meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out_dir)

    # Deterministic two-run: build once into the target dir, once into a temp
    # dir, and require every content file to be byte-identical (SHA-equal).
    sha1, meta1 = build_artifacts(out_dir)
    tmp = tempfile.mkdtemp(prefix="clean24_smoke_run2_")
    try:
        sha2, meta2 = build_artifacts(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    deterministic = (sha1 == sha2
                     and json.dumps(meta1, sort_keys=True)
                     == json.dumps(meta2, sort_keys=True))
    if not deterministic:
        raise SystemExit("deterministic two-run SHA mismatch: not identical")

    # Build report (metadata + per-sample metrics; no file SHAs, no self SHA).
    report = {
        "deterministic_two_run": "PASS",
        "global_K": K,
        "edge_policy": EDGE,
        "guard": GUARD,
        "complex_count": COMPLEX_COUNT,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "target_rms": TARGET_RMS,
        "split_role": SPLIT_ROLE,
        "snr_db": SNR_DB,
        "selection_rule": SELECTION_RULE,
        "input_dataset": os.path.basename(DATASET_PATH),
        "input_dataset_sha256": EXPECTED_DATASET_SHA,
        "input_predictions_tsv": os.path.basename(PRED_TSV_PATH),
        "input_predictions_tsv_sha256": EXPECTED_PRED_SHA,
        "contract_sha256": EXPECTED_CONTRACT_SHA,
        "d2_authority_sha256": EXPECTED_AUTHORITY_SHA,
        "n_samples": meta1["n_samples"],
        "raw24_class_coverage": meta1["raw24_class_coverage"],
        "deployed23_class_coverage": meta1["deployed23_class_coverage"],
        "clip_count_zero": meta1["clip_count_zero"],
        "label_correct": meta1["label_correct"],
        "amssb_merged_count": meta1["amssb_merged_count"],
        "per_sample": meta1["per_sample"],
    }
    report_path = os.path.join(out_dir, "clean24_smoke_build_report.json")
    with open(report_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    # SHA sidecar: every content file in out_dir EXCEPT itself.
    report_sha = sha256_file(report_path)
    sha1["clean24_smoke_build_report.json"] = report_sha
    n_binaries = n_tsvs = 0
    for name in sha1:
        if name.endswith(".ci16") or name.endswith(".f32"):
            n_binaries += 1
        elif name.endswith(".tsv"):
            n_tsvs += 1
    if n_binaries != 72 or n_tsvs != 6:
        raise SystemExit("expected 72 binaries + 6 TSVs, got %d + %d"
                         % (n_binaries, n_tsvs))
    sidecar = os.path.join(out_dir, "clean24_smoke_SHA256SUMS.txt")
    with open(sidecar, "w", encoding="utf-8", newline="\n") as fh:
        for name in sorted(sha1):
            fh.write("%s  %s\n" % (sha1[name], name))

    print("CLEAN24_SMOKE_BUILD result=PASS deterministic_two_run=PASS "
          "label_correct=%s coverage_raw24=%s coverage_deployed23=%s "
          "clip_count_zero=%s content_files=%d"
          % (meta1["label_correct"], meta1["raw24_class_coverage"],
             meta1["deployed23_class_coverage"], meta1["clip_count_zero"],
             len(sha1)))
    for p in meta1["per_sample"]:
        print("  %s source_index=%d seed=%d margin=%.6f tx_scale=%.12g "
              "tx_peak=%.6f clip=%d frozen_deployed23=%d"
              % (p["raw24_label"], p["source_index"], p["seed"], p["margin"],
                 p["tx_scale"], p["tx_peak"], p["clip_count"],
                 p["frozen_deployed23_pred"]))
    print("wrote %d files to %s" % (len(sha1) + 1, out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
