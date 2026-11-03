#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aggregate_fix10class24_singlesdr_ab1_forced.py -- fix10class24-singlesdr-ab1 (task book
39e5) offline aggregator for the FOUR A/B metrics of the SINGLE-SDR 24-class BF16
self-loopback runner.

The board runner (iq_rf_loopback_24class_bf16_fix10.hpp) reports three of the four
metrics directly (coverage / gated_accuracy / end_to_end_accuracy) and prints
`forced_raw24_accuracy=PENDING` because it has no Host-BF16 forced classifier.  This
script completes the fourth metric by:

  1. reading the runner's per-sample results TSV (the authoritative gated record) and
     cross-checking it against the runner's summary.json;
  2. enumerating the gate-refused dumps under <out_dir>/failed_rx/*/ DYNAMICALLY
     (0..24 of them -- nothing is hardcoded to 20 or to a fixed archive SHA);
  3. for each gate-refused dump, exporting the gate-bypassed provisional model input
     with replay_fix10class24_failed_rx_force_classify.sh, then running the FROZEN
     BF16 model on the Host backend (icraft-run.exe, >= 2 forwards) to produce a raw24
     prediction (layer HOST_BF16_FORCED_CLASSIFICATION);
  4. merging gated (board-NPU) + forced (Host-BF16) correct counts into the four
     metrics.  The forced_raw24_accuracy is HYBRID evidence and is labelled
     HYBRID_BOARD_GATED_PLUS_HOST_FORCED -- never a pure board-NPU 24-class accuracy.

Red lines: does not touch the board, does not modify the production 0.100 gate, the
recovery core, the runner, the model, the label order, the canonical assets, or the TX
safety ceiling.  A 24/24 forced result can at most be labelled EVIDENCE, never
RF_PASS / NEW_PRODUCTION_THRESHOLD.

Usage:
  # self-test (pure aggregation math over synthetic 0/3/24 fixtures; no board, no
  # icraft-run, no model):
  python3 scripts/aggregate_fix10class24_singlesdr_ab1_forced.py --self-test

  # the real aggregate (run on the Windows host, or anywhere icraft-run.exe runs):
  python3 scripts/aggregate_fix10class24_singlesdr_ab1_forced.py
      --phase aggregate
      --out-dir DIR                   # runner --out-dir (results TSV + summary.json + failed_rx/)
      --clean24-dir DIR               # clean24_smoke (for the force-classify export)
      --baseline FILE                 # clean24_smoke_raw24_bf16_baseline.tsv
      --icraft-run EXE                # path to icraft-run.exe (Host backend)
      --model-dir DIR                 # dir holding rml24_adamrv11_bf16.json/.raw
      --force-classify-tool FILE      # replay_fix10class24_failed_rx_force_classify.sh
      [--export-dir DIR]              # force-classify export scratch (default <out>/forced_classify_export)
      [--results-dir DIR]             # aggregate outputs (default <out>/forced_aggregate)
"""
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------------------
# constants (frozen contract values, identical to the reference audit)
# ----------------------------------------------------------------------------
NETWORK_NAME = "model_24class"
EXPECT_CLASS_COUNT = 24

# Forced per-sample layer (Host BF16, not the board NPU).  The *merged* metric is the
# HYBRID label below.
FORCED_LAYER = "HOST_BF16_FORCED_CLASSIFICATION"
# The forced_raw24_accuracy metric combines board-NPU gated + Host-BF16 forced rows.
METRIC_LAYER = "HYBRID_BOARD_GATED_PLUS_HOST_FORCED"

FROZEN_MODEL_JSON_SHA256 = (
    "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
)
FROZEN_MODEL_RAW_SHA256 = (
    "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
)

# The runner's per-sample results TSV (22 columns), written verbatim by
# iq_rf_loopback_24class_bf16_fix10.hpp.
RESULTS_TSV_NAME = "route_f_fix10class24_bf16_singlesdr_ab1_results.tsv"
SUMMARY_JSON_NAME = "route_f_fix10class24_bf16_singlesdr_ab1_summary.json"

RESULTS_HEADER = [
    "file_name", "source_index", "raw24_class", "modulation", "snr_db",
    "split_role", "valid", "raw24_pred", "baseline_pred", "correct",
    "prediction_agreement", "repeat_deterministic", "training_corr",
    "training_residual", "timing_offset", "gain_mag", "phase_deg",
    "coarse_cfo_hz", "fine_cfo_hz", "total_cfo_hz", "sro_ppm", "rf_verdict",
]

# clean24_smoke_raw24_bf16_baseline.tsv 7 columns.
BASELINE_HEADER = [
    "source_index", "original_sha256", "raw24_class", "modulation",
    "split_role", "frozen_bf16_raw24_pred", "model_sha256",
]

# The 7 files every failed_rx/<source_index>/ dump must contain (same layout as the
# dual-SDR runner).  The force-classify tool is what actually reads them; this script
# only asserts their presence fail-closed before delegating.
REQUIRED_DUMP_FILES = [
    "raw_rx_ci16le.bin",
    "expected_scaled_payload_ci16le.bin",
    "expected_full_burst_ci16le.bin",
    "coarse_corrected_rx_cf64le.bin",
    "recovered_payload_f32le.bin",
    "recovery_diagnostics.json",
    "SHA256SUMS.txt",
]


# ----------------------------------------------------------------------------
# small helpers (reused verbatim from audit_fix10class24_full24_failed_rx_forceclass1.py)
# ----------------------------------------------------------------------------
def fail(msg):
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fix_nan_literals(text):
    parts = re.split(r'("(?:[^"\\]|\\.)*")', text)
    for i, p in enumerate(parts):
        if p.startswith('"'):
            continue
        p = re.sub(r"\bnan\b", "NaN", p)
        p = re.sub(r"\binf\b", "Infinity", p)
        p = re.sub(r"\b-inf\b", "-Infinity", p)
        parts[i] = p
    return "".join(parts)


def load_json_nan_tolerant(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = _fix_nan_literals(text)

    def _const(s):
        m = {"NaN": float("nan"), "Infinity": float("inf"),
             "-Infinity": float("-inf")}
        if s in m:
            return m[s]
        raise ValueError("unexpected constant %r" % s)

    return json.loads(text, parse_constant=_const)


def read_tsv(path):
    if not os.path.isfile(path):
        fail("TSV not found: %s" % path)
    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = [ln.rstrip("\n") for ln in f]
    if not lines:
        fail("empty TSV: %s" % path)
    header = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != len(header):
            fail("TSV %s row has %d cols (want %d)" % (path, len(f), len(header)))
        rows.append(dict(zip(header, f)))
    return header, rows


# ----------------------------------------------------------------------------
# results-TSV parsing (the authoritative gated record)
# ----------------------------------------------------------------------------
def parse_results_tsv(path):
    header, rows = read_tsv(path)
    if header != RESULTS_HEADER:
        fail("results TSV header mismatch (got %d cols, want the 22-col "
             "singlesdr schema)" % len(header))
    by_index = {}
    for r in rows:
        sid = int(r["source_index"])
        if sid in by_index:
            fail("duplicate source_index=%d in results TSV" % sid)
        r["valid"] = int(r["valid"])
        r["correct"] = int(r["correct"])
        r["raw24_class"] = int(r["raw24_class"])
        r["raw24_pred"] = int(r["raw24_pred"])
        by_index[sid] = r
    return by_index


# ----------------------------------------------------------------------------
# the pure four-metric merge (shared by aggregate + self-test)
# ----------------------------------------------------------------------------
def compute_four_metrics(results_by_index, forced_results, total):
    """results_by_index: {source_index: row} from the runner TSV (row has
    'valid' and 'correct'); forced_results: list of per-sample dicts each with
    'source_index' and 'label_correct'; total: holdout count.

    Definitions are EXACTLY the runner's (iq_rf_loopback_24class_bf16_fix10.hpp):
      coverage             = scored / total
      gated_accuracy       = label_correct / scored            (0 when scored==0)
      end_to_end_accuracy  = label_correct / total
      forced_raw24_accuracy= (label_correct + forced_correct) / total
    where scored == count(valid==1) and label_correct == count(valid==1 && correct==1).
    """
    gated = [r for r in results_by_index.values() if r["valid"] == 1]
    gated_correct = sum(1 for r in gated if r["correct"] == 1)
    forced_correct = sum(1 for f in forced_results if int(f["label_correct"]) == 1)

    coverage = len(gated) / total if total else 0.0
    gated_accuracy = gated_correct / len(gated) if len(gated) else 0.0
    end_to_end_accuracy = gated_correct / total if total else 0.0
    forced_raw24_accuracy = (gated_correct + forced_correct) / total if total else 0.0

    return {
        "total": total,
        "scored": len(gated),
        "gated_correct": gated_correct,
        "forced_count": len(forced_results),
        "forced_correct": forced_correct,
        "coverage": coverage,
        "gated_accuracy": gated_accuracy,
        "end_to_end_accuracy": end_to_end_accuracy,
        "forced_raw24_accuracy": forced_raw24_accuracy,
    }


# ----------------------------------------------------------------------------
# host BF16 inference (verbatim from the reference audit)
# ----------------------------------------------------------------------------
def run_host_infer(icraft_run, model_json, model_raw, input_bin, workdir):
    log_path = workdir / "logs"
    cmd = [
        str(icraft_run),
        "--json", str(model_json),
        "--raw", str(model_raw),
        "--network", NETWORK_NAME,
        "--input", str(input_bin),
        "--backends", "Host",
        "--dump_output",
        "--log_path", str(log_path),
    ]
    proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True)
    if proc.returncode != 0:
        fail("icraft-run exit %d: %s" % (proc.returncode,
                                         proc.stderr.decode("utf-8", "replace")[-2000:]))
    ftmp_dir = log_path / NETWORK_NAME / "ftmpHQB"
    ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
    if len(ftmps) != 1:
        fail("expected exactly 1 ftmp under %s, got %d" % (ftmp_dir, len(ftmps)))
    raw = ftmps[0].read_bytes()
    if len(raw) != EXPECT_CLASS_COUNT * 4:
        fail("ftmp %s is %d bytes (want %d)" % (ftmps[0].name, len(raw),
                                                EXPECT_CLASS_COUNT * 4))
    logits = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    return raw, logits


def classify_one_sample(icraft_run, model_json, model_raw, input_bin, n_passes=2):
    passes = []
    for _ in range(n_passes):
        with tempfile.TemporaryDirectory() as td:
            raw, logits = run_host_infer(icraft_run, model_json, model_raw,
                                         input_bin, Path(td))
        passes.append({
            "raw": raw,
            "logits": logits,
            "argmax": int(np.argmax(logits)),
            "finite": bool(np.all(np.isfinite(logits))),
        })
    return passes


# ----------------------------------------------------------------------------
# force-classify export (delegates to the board-proven replay tool)
# ----------------------------------------------------------------------------
def run_force_classify_export(force_tool, dump_dir, clean24_dir, export_dir):
    cmd = ["bash", str(force_tool), "--dump-dir", str(dump_dir),
           "--clean24-dir", str(clean24_dir), "--export-dir", str(export_dir)]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        fail("force-classify export failed for %s (rc=%d): %s" %
             (dump_dir, proc.returncode,
              proc.stderr.decode("utf-8", "replace")[-2000:]))


# ----------------------------------------------------------------------------
# aggregate phase
# ----------------------------------------------------------------------------
def phase_aggregate(args):
    out_dir = os.path.abspath(args.out_dir)
    results_tsv = os.path.join(out_dir, RESULTS_TSV_NAME)
    summary_json = os.path.join(out_dir, SUMMARY_JSON_NAME)
    failed_rx_dir = os.path.join(out_dir, "failed_rx")

    icraft_run = Path(args.icraft_run) if args.icraft_run else None
    model_dir = Path(args.model_dir) if args.model_dir else None
    clean24_dir = os.path.abspath(args.clean24_dir)
    baseline_path = args.baseline
    force_tool = os.path.abspath(args.force_classify_tool) if args.force_classify_tool else None
    export_dir = os.path.abspath(args.export_dir) if args.export_dir \
        else os.path.join(out_dir, "forced_classify_export")
    results_dir = os.path.abspath(args.results_dir) if args.results_dir \
        else os.path.join(out_dir, "forced_aggregate")

    if not os.path.isfile(results_tsv):
        fail("runner results TSV not found: %s" % results_tsv)
    if not os.path.isdir(failed_rx_dir):
        # 0 gate-refused samples: no failed_rx/ directory at all.
        failed_indexes = []
    else:
        failed_indexes = sorted(
            int(d) for d in os.listdir(failed_rx_dir)
            if os.path.isdir(os.path.join(failed_rx_dir, d))
        )

    results = parse_results_tsv(results_tsv)
    total = len(results)
    if total == 0:
        fail("results TSV is empty (no holdout rows)")

    # cross-check the runner's summary.json when present
    if os.path.isfile(summary_json):
        s = load_json_nan_tolerant(summary_json)
        if int(s.get("holdout_files", -1)) != total:
            fail("summary.json holdout_files=%s != results TSV rows=%d" %
                 (s.get("holdout_files"), total))

    refused = sorted(sid for sid, r in results.items() if r["valid"] == 0)
    # The dump set must be a SUBSET of the refused set (RF_NO_VALID_WINDOW / fatal
    # refusals produce no dump).  A dump for a source_index the runner scored is a
    # hard inconsistency.
    for sid in failed_indexes:
        if sid not in results:
            fail("failed_rx/%d not present in the results TSV" % sid)
        if results[sid]["valid"] == 1:
            fail("failed_rx/%d is a GATED (valid=1) sample -- dump/TSV inconsistent" % sid)
    not_forceable = [sid for sid in refused if sid not in failed_indexes]

    # baseline pairing
    _, b_rows = read_tsv(baseline_path)
    baseline_pred = {}
    for r in b_rows:
        baseline_pred[int(r["source_index"])] = int(r["frozen_bf16_raw24_pred"])
    missing = [sid for sid in failed_indexes if sid not in baseline_pred]
    if missing:
        fail("baseline missing source_index=%s" % missing)

    # model identity
    if not icraft_run or not icraft_run.is_file():
        fail("--icraft-run not found")
    if not model_dir:
        fail("--model-dir required")
    model_json = model_dir / "rml24_adamrv11_bf16.json"
    model_raw = model_dir / "rml24_adamrv11_bf16.raw"
    if not model_json.is_file() or not model_raw.is_file():
        fail("model json/raw not found under %s" % model_dir)
    if sha256_of(str(model_json)) != FROZEN_MODEL_JSON_SHA256:
        fail("model json SHA mismatch (not the frozen BF16 model): %s" % model_json)
    if sha256_of(str(model_raw)) != FROZEN_MODEL_RAW_SHA256:
        fail("model raw SHA mismatch (not the frozen BF16 model): %s" % model_raw)
    if not force_tool or not os.path.isfile(force_tool):
        fail("--force-classify-tool not found")

    # (1) export each gate-refused dump -> model_input_f32le.bin + forced_recovery.json
    os.makedirs(export_dir, exist_ok=True)
    for sid in failed_indexes:
        dump_dir = os.path.join(failed_rx_dir, str(sid))
        for f in REQUIRED_DUMP_FILES:
            if not os.path.isfile(os.path.join(dump_dir, f)):
                fail("failed_rx/%d missing %s" % (sid, f))
        run_force_classify_export(force_tool, dump_dir, clean24_dir, export_dir)

    # (2) locate exports + host-BF16 forced classification (>= 2 forwards)
    forced_rows = []
    logit_rows = []
    # export layout: <export_dir>/<capture_id>/<source_index>/{model_input_f32le.bin,
    # forced_recovery.json} -- capture_id is derived by the tool from dump_dir's
    # grandparent, so collect by walking two levels.
    export_samples = []
    for cap in sorted(os.listdir(export_dir)):
        cap_path = os.path.join(export_dir, cap)
        if not os.path.isdir(cap_path):
            continue
        for idx in sorted(os.listdir(cap_path)):
            idx_path = os.path.join(cap_path, idx)
            if not os.path.isdir(idx_path):
                continue
            mi = os.path.join(idx_path, "model_input_f32le.bin")
            jp = os.path.join(idx_path, "forced_recovery.json")
            if not os.path.isfile(mi) or not os.path.isfile(jp):
                continue
            export_samples.append((cap, int(idx), idx_path, mi, jp))

    export_indexes = sorted(x[1] for x in export_samples)
    if len(set(export_indexes)) != len(export_indexes):
        fail("duplicate export source_index detected")
    if export_indexes != failed_indexes:
        fail("export source_index set %s != failed_rx dump set %s" %
             (export_indexes, failed_indexes))

    for cap, idx, idx_path, mi, jp in sorted(export_samples, key=lambda s: s[1]):
        j = load_json_nan_tolerant(jp)
        if int(j.get("source_index", -1)) != idx:
            fail("forced_recovery.json source_index %s != dir %d" %
                 (j.get("source_index"), idx))
        sc = results[idx]["raw24_class"]
        if int(j.get("source_class", -1)) != sc:
            fail("source_index=%d forced source_class %s != results raw24_class %d" %
                 (idx, j.get("source_class"), sc))

        mi_bytes = open(mi, "rb").read()
        if len(mi_bytes) != 2 * 1024 * 4:
            fail("model_input_f32le.bin size %d != 8192: %s" % (len(mi_bytes), mi))
        mi_arr = np.frombuffer(mi_bytes, dtype="<f4")
        input_finite = bool(np.all(np.isfinite(mi_arr)))

        passes = classify_one_sample(icraft_run, model_json, model_raw, Path(mi), n_passes=2)
        p1, p2 = passes[0], passes[1]
        pred1 = p1["argmax"]
        pred2 = p2["argmax"]
        bpred = baseline_pred[idx]
        baseline_agreement = 1 if pred1 == bpred else 0
        label_correct = 1 if pred1 == sc else 0
        finite = 1 if (p1["finite"] and p2["finite"] and input_finite) else 0
        repeat_argmax = 1 if pred1 == pred2 else 0
        repeat_logits_byte = 1 if p1["raw"] == p2["raw"] else 0

        sorted_logits = np.sort(p1["logits"])[::-1]
        top2 = float(sorted_logits[1]) if len(sorted_logits) > 1 else float("nan")
        margin = float(sorted_logits[0] - sorted_logits[1]) if len(sorted_logits) > 1 else float("nan")

        logit_rows.append({
            "source_index": idx,
            "source_class": sc,
            **{"logit_%02d" % k: ("%.17g" % p1["logits"][k])
               for k in range(EXPECT_CLASS_COUNT)},
            "raw24_pred_pass1": pred1,
            "raw24_pred_pass2": pred2,
        })
        forced_rows.append({
            "source_index": idx,
            "source_class": sc,
            "modulation": results[idx]["modulation"],
            "baseline_pred": bpred,
            "raw24_pred_pass1": pred1,
            "raw24_pred_pass2": pred2,
            "baseline_agreement": baseline_agreement,
            "label_correct": label_correct,
            "finite": finite,
            "repeat_argmax_deterministic": repeat_argmax,
            "repeat_logits_byte_identical": repeat_logits_byte,
            "top1_logit": "%.9g" % float(np.max(p1["logits"])),
            "top2_logit": "%.9g" % top2,
            "margin": "%.9g" % margin,
            "payload_training_residual": j.get("payload_training_residual", ""),
            "payload_training_corr": j.get("payload_training_corr", ""),
            "raw_rx_sha256": j.get("raw_rx_sha256", ""),
            "model_input_sha256": hashlib.sha256(mi_bytes).hexdigest(),
            "result_layer": FORCED_LAYER,
        })

    # (3) merge into the four metrics
    metrics = compute_four_metrics(results, forced_rows, total)

    os.makedirs(results_dir, exist_ok=True)

    with open(os.path.join(results_dir, "raw24_logits.tsv"), "w",
              encoding="utf-8", newline="") as f:
        logit_cols = ["source_index", "source_class"] + \
                     ["logit_%02d" % k for k in range(EXPECT_CLASS_COUNT)] + \
                     ["raw24_pred_pass1", "raw24_pred_pass2"]
        f.write("\t".join(logit_cols) + "\n")
        for r in sorted(logit_rows, key=lambda r: r["source_index"]):
            f.write("\t".join(str(r[c]) for c in logit_cols) + "\n")

    res_cols = ["source_index", "source_class", "modulation", "baseline_pred",
                "raw24_pred_pass1", "raw24_pred_pass2", "baseline_agreement",
                "label_correct", "finite", "repeat_argmax_deterministic",
                "repeat_logits_byte_identical", "top1_logit", "top2_logit", "margin",
                "payload_training_residual", "payload_training_corr",
                "raw_rx_sha256", "model_input_sha256", "result_layer"]
    with open(os.path.join(results_dir, "per_sample_results.tsv"), "w",
              encoding="utf-8", newline="") as f:
        f.write("\t".join(res_cols) + "\n")
        for r in sorted(forced_rows, key=lambda r: r["source_index"]):
            f.write("\t".join(str(r[c]) for c in res_cols) + "\n")

    n = metrics["forced_count"]
    n_correct = metrics["forced_correct"]
    n_agree = sum(r["baseline_agreement"] for r in forced_rows)
    n_finite = sum(r["finite"] for r in forced_rows)
    n_repeat_argmax = sum(r["repeat_argmax_deterministic"] for r in forced_rows)
    n_repeat_byte = sum(r["repeat_logits_byte_identical"] for r in forced_rows)
    all_correct = n > 0 and n_correct == n and n_agree == n and n_finite == n
    conclusion = ("EVIDENCE_SUPPORTS_PROSPECTIVE_GATE_RELAXATION" if all_correct
                  else "EVIDENCE_AGAINST_GATE_RELAXATION") if n > 0 \
        else "NO_FORCED_SAMPLES"

    summary = {
        "task_id": "fix10class24-singlesdr-ab1",
        "status": "M29-RML24-FIX10CLASS24-SINGLESDR-AB1-FORCED-AGGREGATE",
        "forced_layer": FORCED_LAYER,
        "metric_layer": METRIC_LAYER,
        "results_tsv": results_tsv,
        "summary_json": summary_json,
        "failed_rx_dir": failed_rx_dir,
        "forced_count": n,
        "not_forceable_refused": not_forceable,
        "baseline_agreement": "%d/%d" % (n_agree, n),
        "forced_label_correct": "%d/%d" % (n_correct, n),
        "finite": "%d/%d" % (n_finite, n),
        "repeat_argmax_deterministic": "%d/%d" % (n_repeat_argmax, n),
        "repeat_logits_byte_identical": "%d/%d" % (n_repeat_byte, n),
        "production_gate_modified": 0,
        "production_threshold": 0.100,
        "conclusion": conclusion,
        "selection_bias": "FAILURE_CONDITIONAL_SAMPLE",
        "four_metrics": metrics,
        "forced_raw24_accuracy_layer": METRIC_LAYER,
    }
    with open(os.path.join(results_dir, "summary.json"), "w",
              encoding="utf-8", newline="") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")

    print("AGGREGATE_OK total=%d scored=%d gated_correct=%d forced=%d "
          "forced_correct=%d not_forceable=%d coverage=%.4f gated_accuracy=%.4f "
          "end_to_end_accuracy=%.4f forced_raw24_accuracy=%.4f "
          "forced_layer=%s metric_layer=%s conclusion=%s" %
          (metrics["total"], metrics["scored"], metrics["gated_correct"], n,
           n_correct, len(not_forceable), metrics["coverage"],
           metrics["gated_accuracy"], metrics["end_to_end_accuracy"],
           metrics["forced_raw24_accuracy"], FORCED_LAYER, METRIC_LAYER, conclusion))
    return 0


# ----------------------------------------------------------------------------
# self-test (proves 0/3/24 are handled with NO hardcoded count or archive SHA)
# ----------------------------------------------------------------------------
def _write_results_tsv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(RESULTS_HEADER) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]) for c in RESULTS_HEADER) + "\n")


def _mk_refused_row(sid, sc, mod):
    return {
        "file_name": "clean_%s_%s.ci16" % (mod.lower(), sid),
        "source_index": sid,
        "raw24_class": sc,
        "modulation": mod,
        "snr_db": "18",
        "split_role": "holdout",
        "valid": 0, "raw24_pred": -1, "baseline_pred": -1, "correct": -1,
        "prediction_agreement": -1, "repeat_deterministic": -1,
        "training_corr": "0.0", "training_residual": "0.0",
        "timing_offset": -1, "gain_mag": "0.0", "phase_deg": "0.0",
        "coarse_cfo_hz": "0.0", "fine_cfo_hz": "0.0", "total_cfo_hz": "0.0",
        "sro_ppm": "0.0", "rf_verdict": "RF_DISTORTS_IQ",
    }


def _mk_gated_row(sid, sc, mod, correct):
    r = _mk_refused_row(sid, sc, mod)
    r["valid"] = 1
    r["raw24_pred"] = sc if correct else (sc + 1) % EXPECT_CLASS_COUNT
    r["baseline_pred"] = sc
    r["correct"] = 1 if correct else 0
    r["prediction_agreement"] = r["correct"]
    r["repeat_deterministic"] = 1
    r["rf_verdict"] = "RF_PRESERVES_IQ"
    return r


def _self_test_scenario(n_refused):
    total = EXPECT_CLASS_COUNT  # 24
    mods = ["OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
            "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
            "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
            "FM", "GMSK", "OQPSK"]
    sidxs = [i * 500 for i in range(total)]
    rows = []
    refused_sids = []
    for i in range(total):
        sid = sidxs[i]
        if i < n_refused:
            rows.append(_mk_refused_row(sid, i, mods[i]))
            refused_sids.append(sid)
        else:
            # gated correct count chosen so the merge maths is easy to hand-check
            correct = (i % 2 == 0)
            rows.append(_mk_gated_row(sid, i, mods[i], correct))

    # expected forced results: a deterministic subset is "correct" (raw24_class of
    # refused_sids[j] == j, since sidxs[j] == j*500 and raw24_class == index j).
    forced_results = []
    for j, sid in enumerate(refused_sids):
        forced_results.append({
            "source_index": sid, "source_class": j,
            "label_correct": 1 if (j % 3 != 2) else 0,  # deterministic subset correct
        })
    return rows, forced_results, sidxs


def self_test():
    checks = 0
    failures = []

    def check(cond, what):
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(what)

    # enumerate_failed_rx equivalent: dynamic 0/3/24 collection from a synthetic tree
    for n_refused in (0, 3, 24):
        with tempfile.TemporaryDirectory() as td:
            out_dir = os.path.join(td, "run_out")
            os.makedirs(out_dir, exist_ok=True)
            rows, forced_results, sidxs = _self_test_scenario(n_refused)
            results_tsv = os.path.join(out_dir, RESULTS_TSV_NAME)
            _write_results_tsv(results_tsv, rows)

            # build failed_rx/<idx>/ dirs for the refused samples (empty dirs suffice
            # for the enumeration test)
            failed_rx_dir = os.path.join(out_dir, "failed_rx")
            refused_sids = [sidxs[i] for i in range(n_refused)]
            for sid in refused_sids:
                os.makedirs(os.path.join(failed_rx_dir, str(sid)), exist_ok=True)

            # dynamic enumeration
            if os.path.isdir(failed_rx_dir):
                enumerated = sorted(int(d) for d in os.listdir(failed_rx_dir)
                                    if os.path.isdir(os.path.join(failed_rx_dir, d)))
            else:
                enumerated = []
            check(sorted(enumerated) == refused_sids,
                  "enum n_refused=%d got %s want %s" % (n_refused, enumerated, refused_sids))

            # parse + merge
            by_index = parse_results_tsv(results_tsv)
            check(len(by_index) == 24, "parse n_refused=%d total==24" % n_refused)
            metrics = compute_four_metrics(by_index, forced_results, 24)

            # hand-computed expecteds
            gated = 24 - n_refused
            gated_correct = sum(1 for i in range(n_refused, 24) if i % 2 == 0)
            forced_correct = sum(1 for j in range(n_refused) if j % 3 != 2)
            exp_coverage = gated / 24.0
            exp_gated = gated_correct / gated if gated else 0.0
            exp_e2e = gated_correct / 24.0
            exp_forced = (gated_correct + forced_correct) / 24.0

            check(abs(metrics["coverage"] - exp_coverage) < 1e-12,
                  "coverage n_refused=%d" % n_refused)
            check(abs(metrics["gated_accuracy"] - exp_gated) < 1e-12,
                  "gated_accuracy n_refused=%d" % n_refused)
            check(abs(metrics["end_to_end_accuracy"] - exp_e2e) < 1e-12,
                  "e2e n_refused=%d" % n_refused)
            check(abs(metrics["forced_raw24_accuracy"] - exp_forced) < 1e-12,
                  "forced_raw24 n_refused=%d" % n_refused)
            check(metrics["scored"] == gated, "scored n_refused=%d" % n_refused)
            check(metrics["forced_count"] == n_refused, "forced_count n_refused=%d" % n_refused)

    # sanity: 24-refused case must yield gated_accuracy == 0 (division-by-zero guard)
    rows, forced_results, sidxs = _self_test_scenario(24)
    by_index = {r["source_index"]: r for r in rows}
    m24 = compute_four_metrics(by_index, forced_results, 24)
    check(m24["gated_accuracy"] == 0.0 and m24["coverage"] == 0.0,
          "24-refused gated_accuracy/coverage == 0")

    if failures:
        for f in failures:
            sys.stderr.write("SELF-TEST FAIL: %s\n" % f)
        print("SELF_TEST_RESULT checks=%d failures=%d" % (checks, len(failures)))
        return 1
    print("SELF_TEST_RESULT checks=%d failures=0 (0/3/24 all PASS, no hardcoded count)" % checks)
    return 0


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="fix10class24-singlesdr-ab1 four-metric aggregator")
    ap.add_argument("--self-test", action="store_true",
                    help="pure aggregation-math self-test (0/3/24 synthetic fixtures)")
    ap.add_argument("--phase", choices=["aggregate"])
    ap.add_argument("--out-dir", help="runner --out-dir (results TSV + summary.json + failed_rx/)")
    ap.add_argument("--clean24-dir", help="clean24_smoke dir (force-classify export)")
    ap.add_argument("--baseline", help="clean24_smoke_raw24_bf16_baseline.tsv")
    ap.add_argument("--icraft-run", help="path to icraft-run.exe (Host backend)")
    ap.add_argument("--model-dir", help="dir holding rml24_adamrv11_bf16.json/.raw")
    ap.add_argument("--force-classify-tool",
                    help="path to replay_fix10class24_failed_rx_force_classify.sh")
    ap.add_argument("--export-dir", help="force-classify export scratch (default <out>/forced_classify_export)")
    ap.add_argument("--results-dir", help="aggregate outputs (default <out>/forced_aggregate)")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if args.phase == "aggregate":
        if not args.out_dir or not args.clean24_dir or not args.baseline or \
           not args.icraft_run or not args.model_dir or not args.force_classify_tool:
            ap.error("--phase aggregate requires --out-dir, --clean24-dir, --baseline, "
                     "--icraft-run, --model-dir, --force-classify-tool")
        return phase_aggregate(args)

    ap.error("pass --self-test or --phase aggregate")


if __name__ == "__main__":
    sys.exit(main())
