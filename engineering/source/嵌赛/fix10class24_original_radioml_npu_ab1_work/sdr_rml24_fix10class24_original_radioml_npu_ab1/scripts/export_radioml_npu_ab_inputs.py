#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_radioml_npu_ab_inputs.py -- regenerate the 480 frozen original-RadioML test
frames as [2,1024] f32 LE .bin inputs for the board NPU A/B (task
fix10class24-original-radioml-npu-ab1), verify each frame's SHA-256 against the
frozen Host model_input_sha256, and write the 8-column manifest + SHA256SUMS for
the input data package.

Training input contract (FROZEN, verbatim from the Host run):
    arr = np.ascontiguousarray(X[hdf5_row_index].T).astype(np.float32)
    -> [2,1024] f32 little-endian = 8192 bytes; plane 0 = I, plane 1 = Q;
    NO DC removal / normalization / resampling / filtering / augmentation.

Read-only inputs (never modified):
    frozen_test_selection.tsv         (SHA 35b3a32c..., 480 rows, 6 cols)
    host_inference/per_sample_results.tsv (model_input_sha256 + pred_pass1)
    GOLD_XYZ_OSC.0001_1024.hdf5       (SHA e3dd0bef...)

Outputs (input data package root, default <work>/input_package):
    manifest.tsv                      (8 columns)
    SHA256SUMS.txt                    (manifest + all .bin)
    <selection_id>.bin                (480 files, 8192 bytes each)

Red lines: no board / SDR / re-capture / training; no model / preprocessor /
recovery / threshold modification.  Fail-closed on ANY SHA or structural mismatch.
"""
import os
import sys
import hashlib
import argparse

import numpy as np

# ---------------------------------------------------------------------------
# Frozen identities (recorded from prior offline work; NOT re-derived here)
# ---------------------------------------------------------------------------
FROZEN_SELECTION_SHA256 = "35b3a32c8fe94b0a6ef280d309eee8561901e3a22c0bbb87e5c27fd8c4ac9bea"
FROZEN_HDF5_SHA256 = "e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38"

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_HOST_RESULTS = r"F:/嵌赛/fix10class24_original_radioml_accuracy1_work/results"
DEFAULT_HDF5 = r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5"
DEFAULT_OUT = os.path.join(WORK, "input_package")

SELECTION_HEADER = ["selection_id", "hdf5_row_index", "snr_db", "raw24_class",
                    "modulation", "split"]
MANIFEST_HEADER = ["selection_id", "hdf5_row_index", "raw24_class", "modulation",
                   "snr_db", "input_file", "input_sha256", "host_pred"]
N_FRAMES = 480
N_CLASSES = 24
SNR_LEVELS = (0, 10, 20, 30)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_file_lf_normalized(path):
    """SHA-256 over the file content with CRLF line endings normalized to LF.

    The frozen selection identity (35b3a32c...) was recorded over LF-only content;
    a Windows tool re-wrote the on-disk file with CRLF.  The identity that matters
    is the CONTENT (480 rows), not the byte line-ending convention, so we hash the
    LF-normalized bytes exactly as the frozen constant was derived.
    """
    with open(path, "rb") as f:
        raw = f.read()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def fail(msg):
    print("EXPORT_RADIOML_NPU_AB_INPUTS FAIL: " + msg, file=sys.stderr)
    sys.exit(1)


def read_tsv(path, expect_header, n_cols):
    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = [ln.rstrip("\r\n") for ln in f]
    if not lines:
        fail("empty file: " + path)
    header = lines[0].split("\t")
    if header != expect_header:
        fail("header mismatch in %s: got %r" % (path, header))
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f_ = ln.split("\t")
        if len(f_) != n_cols:
            fail("column count %d != %d in %s: %r" % (len(f_), n_cols, path, ln))
        rows.append(f_)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host-results", default=DEFAULT_HOST_RESULTS)
    ap.add_argument("--hdf5", default=DEFAULT_HDF5)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    sel_path = os.path.join(args.host_results, "frozen_test_selection.tsv")
    sha_sel_path = os.path.join(args.host_results, "frozen_test_selection.tsv.sha256")
    per_path = os.path.join(args.host_results, "host_inference", "per_sample_results.tsv")

    # --- identity checks (fail-closed) ---
    if not os.path.isfile(sel_path):
        fail("missing frozen_test_selection.tsv: " + sel_path)
    if sha256_file_lf_normalized(sel_path) != FROZEN_SELECTION_SHA256:
        fail("frozen_test_selection.tsv SHA mismatch (expected %s)" % FROZEN_SELECTION_SHA256)
    if os.path.isfile(sha_sel_path):
        # sanity: the on-disk sidecar must agree with the frozen constant
        with open(sha_sel_path, "r", encoding="utf-8") as f:
            first = f.readline().split()
        if first and first[0] != FROZEN_SELECTION_SHA256:
            fail("frozen_test_selection.tsv.sha256 disagrees with frozen constant")
    if not os.path.isfile(per_path):
        fail("missing per_sample_results.tsv: " + per_path)

    sel = read_tsv(sel_path, SELECTION_HEADER, len(SELECTION_HEADER))
    per = read_tsv(per_path,
                   ["selection_id", "hdf5_row_index", "snr_db", "raw24_class",
                    "modulation", "split", "pred_pass1", "pred_pass2",
                    "label_correct", "finite", "repeat_argmax",
                    "repeat_logits_byte", "top1_logit", "top2_logit", "margin",
                    "model_input_sha256", "result_layer"], 17)

    if len(sel) != N_FRAMES:
        fail("frozen_test_selection.tsv has %d rows (want %d)" % (len(sel), N_FRAMES))
    if len(per) != N_FRAMES:
        fail("per_sample_results.tsv has %d rows (want %d)" % (len(per), N_FRAMES))

    # --- selection invariants ---
    sids = [int(r[0]) for r in sel]
    if sids != list(range(1, N_FRAMES + 1)):
        fail("selection_id not contiguous 1..480")
    row_idx = [int(r[1]) for r in sel]
    if len(set(row_idx)) != N_FRAMES:
        fail("hdf5_row_index not unique across the 480 selection")
    snr_counts = {}
    class_counts = {}
    for r in sel:
        snr = int(r[2])
        cls = int(r[3])
        snr_counts[snr] = snr_counts.get(snr, 0) + 1
        class_counts[cls] = class_counts.get(cls, 0) + 1
    if set(snr_counts.keys()) != set(SNR_LEVELS) or any(snr_counts[s] != 120 for s in SNR_LEVELS):
        fail("per-SNR counts not 120 each: %r" % snr_counts)
    if len(class_counts) != N_CLASSES or any(class_counts[c] != 20 for c in range(N_CLASSES)):
        fail("per-class counts not 20 each: %r" % class_counts)

    # --- host reference (per_sample_results) keyed by hdf5_row_index ---
    host = {}
    for r in per:
        host[int(r[1])] = {"pred_pass1": int(r[6]),
                           "model_input_sha256": r[15],
                           "result_layer": r[16]}

    # --- open HDF5 (read-only) ---
    import h5py
    with h5py.File(args.hdf5, "r") as f:
        X = f["X"]
        if X.shape != (2555904, 1024, 2) or X.dtype != np.float32:
            fail("unexpected HDF5 X shape/dtype: %r %r" % (X.shape, X.dtype))

        os.makedirs(args.out, exist_ok=True)
        manifest_rows = []
        seen_sha = set()
        for r in sel:
            sid = int(r[0])
            hri = int(r[1])
            cls = int(r[3])
            mod = r[4]
            snr = int(r[2])
            if hri not in host:
                fail("hdf5_row_index %d missing from per_sample_results" % hri)
            exp_sha = host[hri]["model_input_sha256"]
            host_pred = host[hri]["pred_pass1"]

            arr = np.ascontiguousarray(X[hri].T).astype(np.float32)
            if arr.shape != (2, 1024):
                fail("frame %d has unexpected tensor shape %r" % (sid, arr.shape))
            raw = arr.tobytes()
            if len(raw) != 8192:
                fail("frame %d has unexpected byte length %d" % (sid, len(raw)))
            got_sha = sha256_bytes(raw)
            if got_sha != exp_sha:
                fail("frame %d (hdf5_row_index=%d) SHA mismatch: got %s want %s"
                     % (sid, hri, got_sha, exp_sha))
            if got_sha in seen_sha:
                fail("input_sha256 not unique (duplicate at frame %d)" % sid)
            seen_sha.add(got_sha)

            fname = "%d.bin" % sid
            with open(os.path.join(args.out, fname), "wb") as of:
                of.write(raw)

            manifest_rows.append([sid, hri, cls, mod, snr, fname, got_sha, host_pred])

    # --- write manifest + SHA256SUMS ---
    with open(os.path.join(args.out, "manifest.tsv"), "w", encoding="utf-8",
              newline="") as mf:
        mf.write("\t".join(MANIFEST_HEADER) + "\n")
        for r in manifest_rows:
            mf.write("\t".join(str(v) for v in r) + "\n")

    sums = []
    for r in manifest_rows:
        fname = r[5]
        sums.append((r[6], fname))
    with open(os.path.join(args.out, "SHA256SUMS.txt"), "w", encoding="utf-8",
              newline="") as sf:
        sf.write("%s  %s\n" % (sha256_file(os.path.join(args.out, "manifest.tsv")),
                               "manifest.tsv"))
        for sha, fname in sums:
            sf.write("%s  %s\n" % (sha, fname))

    print("EXPORT_RADIOML_NPU_AB_INPUTS OK frames=%d out=%s unique_sha=%d"
          % (N_FRAMES, args.out, len(seen_sha)))


if __name__ == "__main__":
    main()
