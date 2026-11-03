#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix10class24-original-radioml-accuracy1 — Phase C: Host BF16 inference.

Feeds the ORIGINAL RadioML2018.01A independent TEST frames (frozen stratified
selection) through the frozen BF16 model via icraft-run.exe --backends Host,
2 forward passes per sample.  The model input is the exact training contract:

    X[row] [1024,2] float32  ->  np.ascontiguousarray(X[row].T)  ->  [2,1024] fp32
    (1024 real f32 then 1024 imag f32, little-endian) = 8192 bytes.

NO dc-removal / normalize / resample / filter / augment.  Layer = HOST_BF16
(CPU reference; NOT board NPU).  Backend = HOST_BF16, never labelled board.

Resumable: per-sample results are appended to results/host_inference/partial.jsonl
as they complete; re-running skips already-completed selection_ids.  A final
per_sample_results.tsv + raw24_logits.tsv + summary.json are written at the end.

Pure stdlib + numpy + h5py.  No torch (FP32 comparison is a separate script).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import h5py
import numpy as np

WORK = Path(r"F:/嵌赛/fix10class24_original_radioml_accuracy1_work")
RESULTS = WORK / "results"
MODEL_TREE = Path(r"F:/嵌赛/fix10class24_tx_rms_sweep1_work/sdr_rml24_fix10class24_tx_rms_sweep1/model_rml24_bf16")
HDF5_PATH = Path(r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5")

MODEL_JSON = MODEL_TREE / "rml24_adamrv11_bf16.json"
MODEL_RAW = MODEL_TREE / "rml24_adamrv11_bf16.raw"
FROZEN_MODEL_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

NETWORK_NAME = "model_24class"
N_CLASSES = 24
N_PASSES = 2
RESULT_LAYER = "HOST_BF16"
INPUT_BYTES = 2 * 1024 * 4  # 8192

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


def read_selection(path: Path) -> list[dict]:
    lines = [ln.rstrip("\r\n") for ln in path.read_text(encoding="utf-8").splitlines()]
    if not lines:
        fatal("empty selection TSV")
    header = lines[0].split("\t")
    if header != SEL_HEADER:
        fatal("selection TSV header mismatch: %r" % header)
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != len(SEL_HEADER):
            fatal("selection row field count mismatch: %r" % ln)
        rows.append({
            "selection_id": int(f[0]),
            "hdf5_row_index": int(f[1]),
            "snr_db": int(f[2]),
            "raw24_class": int(f[3]),
            "modulation": f[4],
            "split": f[5],
        })
    if len(rows) != 480:
        fatal("selection TSV has %d data rows (want 480)" % len(rows))
    return rows


def run_host_infer(icraft_run: Path, model_json, model_raw, input_bin: Path, workdir: str):
    log_path = os.path.join(workdir, "logs")
    cmd = [
        str(icraft_run), "--json", str(model_json), "--raw", str(model_raw),
        "--network", NETWORK_NAME, "--input", str(input_bin),
        "--backends", "Host", "--dump_output", "--log_path", log_path,
    ]
    proc = subprocess.run(cmd, cwd=workdir, capture_output=True)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace")[-2000:]
        out = proc.stdout.decode("utf-8", "replace")[-2000:]
        fatal("icraft-run exit %d\nstdout: %s\nstderr: %s"
              % (proc.returncode, out, err))
    ftmp_dir = os.path.join(log_path, NETWORK_NAME, "ftmpHQB")
    ftmps = ([os.path.join(ftmp_dir, f) for f in os.listdir(ftmp_dir)]
             if os.path.isdir(ftmp_dir) else [])
    if len(ftmps) != 1:
        fatal("expected exactly 1 ftmp under %s, got %d" % (ftmp_dir, len(ftmps)))
    raw = open(ftmps[0], "rb").read()
    if len(raw) != N_CLASSES * 4:
        fatal("ftmp %s is %d bytes (want %d)" % (ftmps[0], len(raw), N_CLASSES * 4))
    logits = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    return raw, logits


def classify_one_sample(icraft_run, model_json, model_raw, input_bin: Path):
    passes = []
    for _ in range(N_PASSES):
        with tempfile.TemporaryDirectory() as td:
            raw, logits = run_host_infer(icraft_run, model_json, model_raw, input_bin, td)
        passes.append({
            "raw": raw,
            "logits": logits,
            "argmax": int(np.argmax(logits)),
            "finite": bool(np.all(np.isfinite(logits))),
        })
    return passes


def process_sample(sel, icraft_run, model_json, model_raw, x_row, y_row, z_val):
    """Preprocess one HDF5 frame and run 2 Host BF16 passes."""
    arr = np.ascontiguousarray(x_row.T).astype(np.float32)
    if arr.shape != (2, 1024):
        fatal("preprocessed shape %s != (2,1024)" % (arr.shape,))
    if not np.all(np.isfinite(arr)):
        fatal("selection %d input non-finite" % sel["selection_id"])
    in_bytes = arr.tobytes()
    if len(in_bytes) != INPUT_BYTES:
        fatal("input bytes %d != %d" % (len(in_bytes), INPUT_BYTES))

    # label / snr cross-check against HDF5 itself
    y_label = int(np.argmax(y_row))
    if y_label != sel["raw24_class"]:
        fatal("selection %d: HDF5 Y argmax %d != selection raw24_class %d"
              % (sel["selection_id"], y_label, sel["raw24_class"]))
    if int(z_val) != sel["snr_db"]:
        fatal("selection %d: HDF5 Z %d != selection snr_db %d"
              % (sel["selection_id"], int(z_val), sel["snr_db"]))

    with tempfile.TemporaryDirectory() as td:
        bin_path = Path(td) / "input.bin"   # .bin (NOT .f32: icraft treats .f32 as image)
        bin_path.write_bytes(in_bytes)
        passes = classify_one_sample(icraft_run, model_json, model_raw, bin_path)

    p1, p2 = passes[0], passes[1]
    return {
        "selection_id": sel["selection_id"],
        "hdf5_row_index": sel["hdf5_row_index"],
        "snr_db": sel["snr_db"],
        "raw24_class": sel["raw24_class"],
        "modulation": sel["modulation"],
        "split": sel["split"],
        "model_input_sha256": hashlib.sha256(in_bytes).hexdigest(),
        "logits": [float(v) for v in p1["logits"]],
        "pred_pass1": p1["argmax"],
        "pred_pass2": p2["argmax"],
        "finite": bool(p1["finite"] and p2["finite"]),
        "repeat_argmax": int(p1["argmax"] == p2["argmax"]),
        "repeat_logits_byte": int(p1["raw"] == p2["raw"]),
        "result_layer": RESULT_LAYER,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--icraft-run", default=r"C:\Icraft\CLI v3.39.0\bin\icraft-run.exe")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="if >0, only process first N (smoke)")
    args = ap.parse_args()

    icraft = Path(args.icraft_run)
    if not icraft.is_file():
        fatal("--icraft-run not found: %s" % icraft)
    if sha256_of(MODEL_JSON) != FROZEN_MODEL_JSON_SHA:
        fatal("model json SHA mismatch (not frozen BF16 model)")
    if sha256_of(MODEL_RAW) != FROZEN_MODEL_RAW_SHA:
        fatal("model raw SHA mismatch (not frozen BF16 model)")

    out_dir = RESULTS / "host_inference"
    out_dir.mkdir(parents=True, exist_ok=True)
    partial_path = out_dir / "partial.jsonl"

    sel_rows = read_selection(RESULTS / "frozen_test_selection.tsv")
    if args.limit > 0:
        sel_rows = sel_rows[: args.limit]

    # resume: load completed selection_ids
    done = {}
    if partial_path.exists():
        for ln in partial_path.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            rec = json.loads(ln)
            done[rec["selection_id"]] = rec
    todo = [r for r in sel_rows if r["selection_id"] not in done]
    print("PHASE_C resume: %d done, %d todo" % (len(done), len(todo)))

    if not todo:
        pass  # nothing to do; fall through to finalize

    h5 = h5py.File(HDF5_PATH, "r")
    try:
        X = h5["X"]
        Y = h5["Y"]
        Z = h5["Z"]

        def work(sel):
            row = int(sel["hdf5_row_index"])
            return process_sample(sel, icraft, MODEL_JSON, MODEL_RAW,
                                  X[row], Y[row], Z[row][0])

        # write partial results incrementally under a lock-free scheme: process in
        # chunks, append to partial.jsonl with explicit flush.
        buf = []
        def flush_buf():
            if buf:
                with partial_path.open("a", encoding="utf-8") as f:
                    for rec in buf:
                        f.write(json.dumps(rec, sort_keys=True) + "\n")
                    f.flush()
                buf.clear()

        if args.workers <= 1:
            for sel in todo:
                rec = work(sel)
                buf.append(rec)
                flush_buf()
                print("  done selection_id=%d class=%d(%s) snr=%d pred=%d" %
                      (rec["selection_id"], rec["raw24_class"], rec["modulation"],
                       rec["snr_db"], rec["pred_pass1"]), flush=True)
        else:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = {ex.submit(work, sel): sel for sel in todo}
                for fut in as_completed(futs):
                    rec = fut.result()
                    buf.append(rec)
                    flush_buf()
    finally:
        h5.close()

    # finalize
    if partial_path.exists():
        all_recs = [json.loads(ln) for ln in partial_path.read_text(encoding="utf-8").splitlines()
                    if ln.strip()]
        all_recs.sort(key=lambda r: r["selection_id"])
    else:
        all_recs = []

    # per_sample_results.tsv
    res_cols = ["selection_id", "hdf5_row_index", "snr_db", "raw24_class",
                "modulation", "split", "pred_pass1", "pred_pass2",
                "label_correct", "finite", "repeat_argmax", "repeat_logits_byte",
                "top1_logit", "top2_logit", "margin", "model_input_sha256",
                "result_layer"]
    res_path = out_dir / "per_sample_results.tsv"
    with res_path.open("w", encoding="utf-8", newline="") as f:
        f.write("\t".join(res_cols) + "\n")
        for r in all_recs:
            lg = np.asarray(r["logits"], dtype=np.float64)
            srt = np.sort(lg)[::-1]
            top1, top2 = float(srt[0]), float(srt[1])
            pred1 = r["pred_pass1"]
            row = [
                r["selection_id"], r["hdf5_row_index"], r["snr_db"], r["raw24_class"],
                r["modulation"], r["split"], pred1, r["pred_pass2"],
                1 if pred1 == r["raw24_class"] else 0, 1 if r["finite"] else 0,
                r["repeat_argmax"], r["repeat_logits_byte"],
                "%.9g" % top1, "%.9g" % top2, "%.9g" % (top1 - top2),
                r["model_input_sha256"], r["result_layer"],
            ]
            f.write("\t".join(str(c) for c in row) + "\n")

    # raw24_logits.tsv
    logit_cols = ["selection_id", "hdf5_row_index", "raw24_class"] + \
                 ["logit_%02d" % k for k in range(N_CLASSES)] + \
                 ["pred_pass1", "pred_pass2"]
    with (out_dir / "raw24_logits.tsv").open("w", encoding="utf-8", newline="") as f:
        f.write("\t".join(logit_cols) + "\n")
        for r in all_recs:
            lg = np.asarray(r["logits"], dtype=np.float64)
            row = [r["selection_id"], r["hdf5_row_index"], r["raw24_class"]] + \
                  ["%.17g" % v for v in lg] + [r["pred_pass1"], r["pred_pass2"]]
            f.write("\t".join(str(c) for c in row) + "\n")

    n = len(all_recs)
    n_correct = sum(1 for r in all_recs if r["pred_pass1"] == r["raw24_class"])
    n_finite = sum(1 for r in all_recs if r["finite"])
    n_repeat = sum(r["repeat_argmax"] for r in all_recs)
    n_byte = sum(r["repeat_logits_byte"] for r in all_recs)
    summary = {
        "task_id": "fix10class24-original-radioml-accuracy1",
        "phase": "C_host_inference",
        "result_layer": RESULT_LAYER,
        "backend": "HOST_BF16",
        "note": ("Host (CPU) frozen BF16 reference inference on ORIGINAL RadioML "
                 "test frames.  NOT a board NPU measurement.  NOT labelled board."),
        "frozen_model_json_sha": FROZEN_MODEL_JSON_SHA,
        "frozen_model_raw_sha": FROZEN_MODEL_RAW_SHA,
        "sample_count": n,
        "expected_total": 480,
        "label_correct": "%d/%d" % (n_correct, n),
        "finite": "%d/%d" % (n_finite, n),
        "repeat_argmax_deterministic": "%d/%d" % (n_repeat, n),
        "repeat_logits_byte_identical": "%d/%d" % (n_byte, n),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("PHASE_C_OK samples=%d correct=%d/%d finite=%d/%d repeat_argmax=%d/%d "
          "repeat_byte=%d/%d layer=%s" %
          (n, n_correct, n, n_finite, n, n_repeat, n, n_byte, n, RESULT_LAYER))
    return 0


if __name__ == "__main__":
    sys.exit(main())
