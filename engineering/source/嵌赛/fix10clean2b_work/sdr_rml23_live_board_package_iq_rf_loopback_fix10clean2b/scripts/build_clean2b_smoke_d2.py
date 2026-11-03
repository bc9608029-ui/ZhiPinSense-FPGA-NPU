#!/usr/bin/env python3
"""build_clean2b_smoke_d2.py -- fix10clean2b Step 1: build the 2-sample clean-IQ
dual-SDR smoke artifacts (clean2b_smoke/).

Takes the clean2a CLEAN generated IQ (formal12000) and, for the two fixed
samples (BPSK source_index=1500, 4ASK source_index=500), produces the exact
Route-D2 NON-training artifacts the board needs for the dual-SDR run:

  clean_<tag>_<sha8>.ci16       interleaved int16 LE (I,Q,I,Q...), AC-ONLY, x20
                                interpolated to 2.56 MSPS (53760 complex =
                                215040 bytes).  This is the exact TX waveform
                                streamed through the Pluto.
  source_clean_<tag>.f32        [2,1024] fp32 planar [real,imag] (8192 bytes),
                                the ORIGINAL clean2a source sample (== the D2
                                original_sha256 identity).
  recovered_tensor_clean_<tag>.f32  [2,1024] fp32 (8192 bytes), the D2 reference:
                                AC re-mapped + DC restored (near-lossless).
  route_d2_rf_manifest.tsv      24 columns (same schema as build_route_d2_rf_
                                artifacts.py), for the Step-3 clean DIGITAL path
                                (iq-clean-iq-23class-fix10, input_kind=
                                radioml-d2-2p56m).
  clean2b_smoke_manifest.tsv    27 columns (24 + tx_scale + frozen_raw24_pred +
                                frozen_deployed23_pred), for the Step-6 dual-SDR
                                path (input_kind=radioml-compatible-clean-d2-2p56m).
  clean2b_smoke_clean_baseline.tsv  6-col CLEAN baseline (Step 3).
  clean2b_smoke_baseline.tsv        6-col fix9r baseline (Step 6).
  clean2b_smoke_build_report.json    metadata only (no self SHA, no file SHAs).
  clean2b_smoke_SHA256SUMS.txt       11 content-file SHAs (no self SHA).

Deterministic: every byte is derived from the frozen HDF5 fp32 sample through the
imported (never re-implemented) analyze_route_d2_4ask.reconstruct / recovered_
tensor_1024.  Two in-process builds must byte-identical (SHA-equal) or the script
fails closed.

Pure stdlib + numpy + h5py (no torch).  Run isolated:  python -I <this file>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile

import numpy as np
import h5py

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_route_d2_4ask as A  # noqa: E402

CONTRACT_DIR = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\contracts"
sys.path.insert(0, CONTRACT_DIR)
from rml23_merged_contract import (  # noqa: E402
    DEPLOYED_LABEL_ORDER_23, SOURCE_LABEL_ORDER_24, SOURCE_TO_DEPLOYED,
    assert_source_order_matches,
)

DATASET_PATH = r"F:/嵌赛/fix10clean2a_dataset/clean24_formal12000.hdf5"
PRED_TSV_PATH = r"F:/嵌赛/fix10clean2a_results/frozen_model_predictions_formal12000.tsv"
DEFAULT_OUT_DIR = r"F:/嵌赛/fix10clean2b_work/clean2b_smoke"

K = 2048.0
EDGE = "zero"
GUARD = 832
COMPLEX_COUNT = 53760
SAMPLE_RATE_HZ = 2560000
SPLIT_ROLE = "holdout"
SNR_DB = "nan"

# (source_index == HDF5 row index == predictions sample_id, seed, modulation,
#  raw24_class, deployed23_class, tag).  Ordered BPSK then 4ASK (== plan order).
SAMPLES = [
    {"source_index": 1500, "seed": 2001500, "modulation": "BPSK",
     "raw24_class": 3, "deployed23_class": 3, "tag": "bpsk"},
    {"source_index": 500, "seed": 2000500, "modulation": "4ASK",
     "raw24_class": 1, "deployed23_class": 1, "tag": "4ask"},
]

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
FIX9R_BASELINE_HEADER = ["source_index", "original_sha256", "deployed_class",
                         "modulation", "split_role", "frozen_baseline_pred"]

CONTENT_BINARIES = 6   # 2 ci16 + 4 f32
CONTENT_TSVS = 4       # route_d2_rf + clean2b_smoke + 2 baselines
CONTENT_JSON = 1       # build_report
# total content files = 11, + 1 SHA sidecar = 12


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def load_predictions(tsv_path: str) -> dict[int, dict]:
    """Parse the 10-column frozen predictions TSV into sample_id -> row dict.

    Fail-closed: a missing or duplicate sample_id raises (never a positional
    lookup, never a silent fallback).
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
                      "correct_deployed23"], "unexpected predictions TSV header: %r" % header
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
            "correct_raw24": int(p[8]), "correct_deployed23": int(p[9]),
        }
    return preds


def build_artifacts(out_dir: str) -> tuple[dict[str, str], dict]:
    """Write the 10 deterministic artifact files (6 binary + 4 TSV) into out_dir.

    Returns (sha_map {relpath -> sha256}, samples_meta).  Does NOT write the
    build report or the SHA sidecar (those are finalised in main()).
    """
    os.makedirs(out_dir, exist_ok=True)

    # Fail closed on the frozen 24-class label contract before any math.
    assert_source_order_matches(SOURCE_LABEL_ORDER_24)

    # Read the two fixed samples from the clean2a HDF5 (short read, deterministic).
    with h5py.File(DATASET_PATH, "r") as f:
        X = f["X"][:]        # [N, 1024, 2] fp32, (t,0)=real (t,1)=imag
        Y = np.asarray(f["Y"]).astype(np.int64)
        seeds = np.asarray(f["seeds"]).astype(np.int64)
        order = json.loads(f.attrs["label_order"])
    if list(order) != list(SOURCE_LABEL_ORDER_24):
        raise SystemExit("HDF5 label_order mismatch vs frozen 24-class order")

    preds = load_predictions(PRED_TSV_PATH)

    manifest_rows_24: list[list[str]] = []
    manifest_rows_27: list[list[str]] = []
    clean_baseline_rows: list[list[str]] = []
    fix9r_baseline_rows: list[list[str]] = []
    sha_map: dict[str, str] = {}
    samples_meta = {"samples": [], "label_correct": "0/0"}

    label_correct = 0
    for out_idx, s in enumerate(SAMPLES):
        row = s["source_index"]
        y = int(Y[row])
        seed = int(seeds[row])
        if y != s["raw24_class"]:
            raise SystemExit("row %d has Y=%d, expected %s(%d)"
                             % (row, y, s["modulation"], s["raw24_class"]))
        if seed != s["seed"]:
            raise SystemExit("row %d has seed=%d, expected %d"
                             % (row, seed, s["seed"]))

        xr = X[row, :, 0].astype(np.float64)
        xi = X[row, :, 1].astype(np.float64)
        x = xr + 1j * xi                                    # 1024 complex

        # Route-D2 reconstruction (imported, never re-implemented).
        r = A.reconstruct(x, "D2", K, edge=EDGE, guard=GUARD)

        ci16 = np.ascontiguousarray(r["iq"], dtype="<i2")    # 53760 complex int16
        source_float = np.ascontiguousarray(X[row].T, dtype="<f4")   # [2,1024] f32
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

        d2_ci16_sha256 = sha256_bytes(ci16.tobytes())
        source_float_sha256 = sha256_bytes(source_float.tobytes())
        recovered_tensor_sha256 = sha256_bytes(recovered_tensor.tobytes())

        # Fail closed: the two identity SHAs must differ (distinct semantics).
        if source_float_sha256 == d2_ci16_sha256:
            raise SystemExit("source_float_sha256 == d2_ci16_sha256 (must differ)")

        tag = s["tag"]
        qname = "clean_%s_%s.ci16" % (tag, d2_ci16_sha256[:8])
        rname = "recovered_tensor_clean_%s.f32" % tag
        sname = "source_clean_%s.f32" % tag
        ci16.tofile(os.path.join(out_dir, qname))
        recovered_tensor.tofile(os.path.join(out_dir, rname))
        source_float.tofile(os.path.join(out_dir, sname))

        # Verify on-disk bytes hash to the recorded SHA (belt and suspenders).
        for name, want in ((qname, d2_ci16_sha256), (rname, recovered_tensor_sha256),
                           (sname, source_float_sha256)):
            got = sha256_file(os.path.join(out_dir, name))
            if got != want:
                raise SystemExit("on-disk SHA mismatch for %s" % name)
            sha_map[name] = got

        native_rms = float(r["quant_rms_counts"])
        tx_peak = float(np.max(np.abs(ci16.astype(np.float64))))
        tx_scale = 2048.0 / native_rms
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
        if pr["raw24_label"] != s["modulation"]:
            raise SystemExit("sample_id %d raw24_label %r != %r"
                             % (s["source_index"], pr["raw24_label"], s["modulation"]))
        frozen_raw24_pred = SOURCE_LABEL_ORDER_24.index(pr["raw24_pred"])
        frozen_deployed23_pred = DEPLOYED_LABEL_ORDER_23.index(pr["deployed23_pred"])
        if pr["correct_raw24"] != 1 or pr["correct_deployed23"] != 1:
            raise SystemExit("sample_id %d not label-correct in predictions TSV"
                             % s["source_index"])
        if frozen_raw24_pred != s["raw24_class"]:
            raise SystemExit("frozen_raw24_pred %d != raw24_class %d for %s"
                             % (frozen_raw24_pred, s["raw24_class"], tag))
        if frozen_deployed23_pred != s["deployed23_class"]:
            raise SystemExit("frozen_deployed23_pred %d != deployed23_class %d for %s"
                             % (frozen_deployed23_pred, s["deployed23_class"], tag))
        label_correct += 1

        cols24 = [
            str(out_idx), str(s["source_index"]), str(s["raw24_class"]),
            str(s["deployed23_class"]), s["modulation"], SNR_DB, SPLIT_ROLE,
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
        clean_baseline_rows.append([
            str(s["source_index"]), qname, d2_ci16_sha256,
            str(s["deployed23_class"]), SPLIT_ROLE, str(frozen_deployed23_pred),
        ])
        fix9r_baseline_rows.append([
            str(s["source_index"]), source_float_sha256, str(s["deployed23_class"]),
            s["modulation"], SPLIT_ROLE, str(frozen_deployed23_pred),
        ])
        samples_meta["samples"].append({
            "source_index": s["source_index"], "seed": s["seed"],
            "modulation": s["modulation"], "raw24_class": s["raw24_class"],
            "deployed23_class": s["deployed23_class"],
            "frozen_raw24_pred": frozen_raw24_pred,
            "frozen_deployed23_pred": frozen_deployed23_pred,
            "tx_scale": tx_scale, "native_rms": native_rms, "tx_peak": tx_peak,
            "clip_count": clip_count,
        })

    samples_meta["label_correct"] = "%d/%d" % (label_correct, len(SAMPLES))
    if label_correct != len(SAMPLES):
        raise SystemExit("label_correct %d/%d != %d/%d"
                         % (label_correct, len(SAMPLES), len(SAMPLES), len(SAMPLES)))

    def _write_tsv(name: str, header: list[str], rows: list[list[str]]) -> None:
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\t".join(header) + "\n")
            for rr in rows:
                fh.write("\t".join(rr) + "\n")
        sha_map[name] = sha256_file(path)

    _write_tsv("route_d2_rf_manifest.tsv", MANIFEST_HEADER, manifest_rows_24)
    _write_tsv("clean2b_smoke_manifest.tsv", MANIFEST_HEADER + EXTRA_HEADER,
               manifest_rows_27)
    _write_tsv("clean2b_smoke_clean_baseline.tsv", CLEAN_BASELINE_HEADER,
               clean_baseline_rows)
    _write_tsv("clean2b_smoke_baseline.tsv", FIX9R_BASELINE_HEADER,
               fix9r_baseline_rows)

    return sha_map, samples_meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out_dir)

    # Deterministic two-run: build once into the target dir, once into a temp
    # dir, and require the 10 content files to be byte-identical (SHA-equal).
    sha1, meta1 = build_artifacts(out_dir)
    tmp = tempfile.mkdtemp(prefix="clean2b_smoke_run2_")
    try:
        sha2, meta2 = build_artifacts(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    deterministic = (sha1 == sha2
                     and json.dumps(meta1, sort_keys=True)
                     == json.dumps(meta2, sort_keys=True))
    if not deterministic:
        raise SystemExit("deterministic two-run SHA mismatch: not identical")

    # Build report (metadata only; no file SHAs, no self SHA).
    report = {
        "deterministic_two_run": "PASS",
        "global_K": K,
        "edge_policy": EDGE,
        "guard": GUARD,
        "complex_count": COMPLEX_COUNT,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "split_role": SPLIT_ROLE,
        "snr_db": SNR_DB,
        "input_dataset": os.path.basename(DATASET_PATH),
        "input_predictions_tsv": os.path.basename(PRED_TSV_PATH),
        "label_correct": meta1["label_correct"],
        "samples": meta1["samples"],
    }
    report_path = os.path.join(out_dir, "clean2b_smoke_build_report.json")
    with open(report_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    # SHA sidecar: 11 content files (10 + build report), never itself.
    report_sha = sha256_file(report_path)
    sha1["clean2b_smoke_build_report.json"] = report_sha
    if len(sha1) != 11:
        raise SystemExit("expected 11 content files, got %d" % len(sha1))
    sidecar = os.path.join(out_dir, "clean2b_smoke_SHA256SUMS.txt")
    with open(sidecar, "w", encoding="utf-8", newline="\n") as fh:
        for name in sorted(sha1):
            fh.write("%s  %s\n" % (sha1[name], name))

    print("CLEAN2B_SMOKE_BUILD result=PASS deterministic_two_run=PASS "
          "label_correct=%s content_files=%d"
          % (meta1["label_correct"], len(sha1)))
    for s in meta1["samples"]:
        print("  %s source_index=%d seed=%d tx_scale=%.12g native_rms=%.6f "
              "tx_peak=%.6f clip=%d frozen_deployed23=%d"
              % (s["modulation"], s["source_index"], s["seed"], s["tx_scale"],
                 s["native_rms"], s["tx_peak"], s["clip_count"],
                 s["frozen_deployed23_pred"]))
    print("wrote 12 files to %s" % out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
