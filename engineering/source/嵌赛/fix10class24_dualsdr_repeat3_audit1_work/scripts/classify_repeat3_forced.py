#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classify_repeat3_forced.py -- fix10class24-dualsdr-repeat3-audit1 Phase C.

Host BF16 inference on the 49 wide-linear-corrected forced exports produced by
replay_fix10class24_force_classify_wl.  DYNAMIC: accepts 0..72 gate-rejected
samples across the 3 rounds -- never hardcodes an index list or archive SHA.

For each forced export (forced_exports/<round>/<source_index>/):
  * verify model_input_f32le.bin is 8192 bytes and finite
  * verify forced_recovery.json identity against the frozen manifest
  * run icraft-run.exe --backends Host TWICE (>=2 forward passes)
  * verify each 24-dim logits vector is finite and the two passes agree
  * record raw24 argmax prediction + baseline agreement + label correct

Red lines: no board / no SDR / no training / no model / recovery / gate change.
Layer label = HOST_BF16_FORCED_CLASSIFICATION (NOT board NPU).  This script does
NOT write RF_PASS / PROJECT_COMPLETE; it only reports per-sample Host predictions.

Pure stdlib + numpy.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROD_TREE = r"F:\嵌赛\fix10class24_tx_rms_sweep1_work\sdr_rml24_fix10class24_tx_rms_sweep1"
MANIFEST = os.path.join(PROD_TREE, "clean24_smoke", "route_d2_rf_manifest.tsv")
BASELINE = os.path.join(PROD_TREE, "baselines", "clean24_smoke_raw24_bf16_baseline.tsv")
MODEL_JSON = os.path.join(PROD_TREE, "model_rml24_bf16", "rml24_adamrv11_bf16.json")
MODEL_RAW = os.path.join(PROD_TREE, "model_rml24_bf16", "rml24_adamrv11_bf16.raw")

FROZEN_MODEL_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

NETWORK_NAME = "model_24class"
N_CLASSES = 24
N_PASSES = 2
HOST_LAYER = "HOST_BF16_FORCED_CLASSIFICATION"

# manifest 26-col schema (route_d2_rf_manifest.tsv, NOT the 27-col clean24 schema)
MANIFEST_HEADER = [
    "sample_index", "source_index", "raw24_class", "deployed23_class",
    "modulation", "snr_db", "split_role", "global_K", "original_dc_i",
    "original_dc_q", "ac_rms", "rec_scale", "complex_count", "sample_rate",
    "tx_rms", "tx_peak", "clip_count", "edge_policy", "guard",
    "original_sha256", "quantized_sha256", "recovered_tensor_sha256",
    "quantized_file", "recovered_tensor_file",
]

BASELINE_HEADER = ["source_index", "original_sha256", "raw24_class", "modulation",
                   "split_role", "frozen_bf16_raw24_pred", "model_sha256"]


def fatal(msg):
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
        p = re.sub(r'\bnan\b', 'NaN', p)
        p = re.sub(r'\binf\b', 'Infinity', p)
        p = re.sub(r'\b-inf\b', '-Infinity', p)
        parts[i] = p
    return "".join(parts)


def load_json_nan_tolerant(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = _fix_nan_literals(text)
    def _const(s):
        m = {"NaN": float("nan"), "Infinity": float("inf"), "-Infinity": float("-inf")}
        if s in m:
            return m[s]
        raise ValueError("unexpected constant %r" % s)
    return json.loads(text, parse_constant=_const)


def read_tsv(path, header_expected):
    if not os.path.isfile(path):
        fatal("TSV not found: %s" % path)
    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = [ln.rstrip("\r\n") for ln in f]
    if not lines:
        fatal("empty TSV: %s" % path)
    header = lines[0].split("\t")
    if header != header_expected:
        fatal("TSV header mismatch:\n got=%r\n exp=%r" % (header, header_expected))
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != len(header):
            fatal("TSV row field count != %d: %r" % (len(header), ln))
        rows.append(dict(zip(header, f)))
    return rows


def load_manifest():
    rows = read_tsv(MANIFEST, MANIFEST_HEADER)
    out = {}
    for r in rows:
        sid = int(r["source_index"])
        out[sid] = {
            "raw24_class": int(r["raw24_class"]),
            "modulation": r["modulation"],
            "file_name": r["quantized_file"],
        }
    if len(out) != N_CLASSES:
        fatal("manifest has %d rows (want %d)" % (len(out), N_CLASSES))
    return out


def load_baseline():
    rows = read_tsv(BASELINE, BASELINE_HEADER)
    out = {}
    for r in rows:
        sid = int(r["source_index"])
        if r["model_sha256"] != FROZEN_MODEL_JSON_SHA:
            fatal("baseline source_index=%d model_sha256 != frozen json sha" % sid)
        out[sid] = int(r["frozen_bf16_raw24_pred"])
    if len(out) != N_CLASSES:
        fatal("baseline has %d rows (want %d)" % (len(out), N_CLASSES))
    return out


def run_host_infer(icraft_run, model_json, model_raw, input_bin, workdir):
    log_path = os.path.join(workdir, "logs")
    cmd = [
        str(icraft_run), "--json", str(model_json), "--raw", str(model_raw),
        "--network", NETWORK_NAME, "--input", str(input_bin),
        "--backends", "Host", "--dump_output", "--log_path", str(log_path),
    ]
    proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace")[-2000:]
        out = proc.stdout.decode("utf-8", "replace")[-2000:]
        fatal("icraft-run exit %d\nstdout: %s\nstderr: %s" % (proc.returncode, out, err))
    ftmp_dir = os.path.join(log_path, NETWORK_NAME, "ftmpHQB")
    ftmps = [os.path.join(ftmp_dir, f) for f in os.listdir(ftmp_dir)] \
        if os.path.isdir(ftmp_dir) else []
    if len(ftmps) != 1:
        fatal("expected exactly 1 ftmp under %s, got %d" % (ftmp_dir, len(ftmps)))
    raw = open(ftmps[0], "rb").read()
    if len(raw) != N_CLASSES * 4:
        fatal("ftmp %s is %d bytes (want %d)" % (ftmps[0], len(raw), N_CLASSES * 4))
    logits = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    return raw, logits


def classify_one_sample(icraft_run, model_json, model_raw, input_bin):
    passes = []
    for _ in range(N_PASSES):
        with tempfile.TemporaryDirectory() as td:
            raw, logits = run_host_infer(icraft_run, model_json, model_raw,
                                         input_bin, td)
        passes.append({
            "raw": raw,
            "logits": logits,
            "argmax": int(np.argmax(logits)),
            "finite": bool(np.all(np.isfinite(logits))),
        })
    return passes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--icraft-run", default=r"C:\Icraft\CLI v3.39.0\bin\icraft-run.exe")
    ap.add_argument("--forced-dir",
                    default=os.path.join(WORK, "results", "forced_exports"))
    ap.add_argument("--out-dir", default=os.path.join(WORK, "results", "host_inference"))
    args = ap.parse_args()

    icraft = Path(args.icraft_run)
    if not icraft.is_file():
        fatal("--icraft-run not found: %s" % icraft)
    if sha256_of(MODEL_JSON) != FROZEN_MODEL_JSON_SHA:
        fatal("model json SHA mismatch (not frozen BF16 model): %s" % MODEL_JSON)
    if sha256_of(MODEL_RAW) != FROZEN_MODEL_RAW_SHA:
        fatal("model raw SHA mismatch (not frozen BF16 model): %s" % MODEL_RAW)

    manifest = load_manifest()
    baseline = load_baseline()

    # ---- dynamic sample collection: <round>/<source_index>/ ----
    samples = []
    rounds = sorted(d for d in os.listdir(args.forced_dir)
                    if os.path.isdir(os.path.join(args.forced_dir, d)))
    for rnd in rounds:
        rp = os.path.join(args.forced_dir, rnd)
        for idx in sorted(os.listdir(rp)):
            ip = os.path.join(rp, idx)
            if not os.path.isdir(ip):
                continue
            mi = os.path.join(ip, "model_input_f32le.bin")
            jp = os.path.join(ip, "forced_recovery.json")
            if not os.path.isfile(mi) or not os.path.isfile(jp):
                fatal("export dir missing model_input/forced_recovery.json: %s" % ip)
            try:
                sid = int(idx)
            except ValueError:
                fatal("non-numeric source_index dir: %r" % idx)
            j = load_json_nan_tolerant(jp)
            samples.append((rnd, sid, ip, mi, j))

    if not samples:
        fatal("no forced exports found under %s" % args.forced_dir)
    keys = set()
    for rnd, sid, *_ in samples:
        if (rnd, sid) in keys:
            fatal("duplicate (round, source_index): %s/%d" % (rnd, sid))
        keys.add((rnd, sid))
    # every forced export must be a genuine gate-rejected sample: production gate
    # not modified, diagnostic bypass marked, merge marker present.
    for rnd, sid, ip, mi, j in samples:
        if int(j.get("production_gate_modified", -1)) != 0:
            fatal("%s/%d production_gate_modified != 0" % (rnd, sid))
        if int(j.get("diagnostic_gate_bypass", -1)) != 1:
            fatal("%s/%d diagnostic_gate_bypass != 1" % (rnd, sid))
        if j.get("merge_marker") != "HYBRID_BOARD_GATED_PLUS_HOST_FORCED":
            fatal("%s/%d bad merge_marker %r" % (rnd, sid, j.get("merge_marker")))
        if j.get("backend") != "HOST_BF16":
            fatal("%s/%d backend != HOST_BF16" % (rnd, sid))

    os.makedirs(args.out_dir, exist_ok=True)

    logit_rows = []
    result_rows = []
    for rnd, sid, ip, mi, j in sorted(samples, key=lambda s: (s[0], s[1])):
        mrow = manifest[sid]
        sc = mrow["raw24_class"]
        mod = mrow["modulation"]
        if int(j["source_class"]) != sc:
            fatal("%s/%d forced_recovery source_class %d != manifest %d"
                  % (rnd, sid, int(j["source_class"]), sc))
        if int(j["source_index"]) != sid:
            fatal("%s/%d forced_recovery source_index %d != dir %d"
                  % (rnd, sid, int(j["source_index"]), sid))

        mi_bytes = open(mi, "rb").read()
        if len(mi_bytes) != 2 * 1024 * 4:
            fatal("%s/%d model_input size %d != 8192" % (rnd, sid, len(mi_bytes)))
        mi_arr = np.frombuffer(mi_bytes, dtype="<f4")
        input_finite = bool(np.all(np.isfinite(mi_arr)))

        bpred = baseline[sid]
        passes = classify_one_sample(icraft, MODEL_JSON, MODEL_RAW, mi)
        p1, p2 = passes[0], passes[1]
        pred1 = p1["argmax"]
        pred2 = p2["argmax"]
        baseline_agreement = 1 if pred1 == bpred else 0
        label_correct = 1 if pred1 == sc else 0
        finite = 1 if (p1["finite"] and p2["finite"] and input_finite) else 0
        repeat_argmax = 1 if pred1 == pred2 else 0
        repeat_logits_byte = 1 if p1["raw"] == p2["raw"] else 0

        top1 = float(np.max(p1["logits"]))
        srt = np.sort(p1["logits"])[::-1]
        top2 = float(srt[1]) if len(srt) > 1 else float("nan")
        margin = float(srt[0] - srt[1]) if len(srt) > 1 else float("nan")

        logit_rows.append({
            "round": rnd, "source_index": sid, "source_class": sc,
            **{"logit_%02d" % k: ("%.17g" % p1["logits"][k]) for k in range(N_CLASSES)},
            "raw24_pred_pass1": pred1, "raw24_pred_pass2": pred2,
        })

        result_rows.append({
            "round": rnd, "source_index": sid, "source_class": sc,
            "modulation": mod, "baseline_pred": bpred,
            "raw24_pred_pass1": pred1, "raw24_pred_pass2": pred2,
            "baseline_agreement": baseline_agreement, "label_correct": label_correct,
            "finite": finite, "repeat_argmax_deterministic": repeat_argmax,
            "repeat_logits_byte_identical": repeat_logits_byte,
            "top1_logit": "%.9g" % top1, "top2_logit": "%.9g" % top2,
            "margin": "%.9g" % margin,
            "payload_training_residual": j.get("payload_training_residual", ""),
            "payload_training_corr": j.get("payload_training_corr", ""),
            "wide_linear_enabled": j.get("wide_linear", {}).get("enabled", ""),
            "raw_rx_sha256": j.get("raw_rx_sha256", ""),
            "model_input_sha256": hashlib.sha256(mi_bytes).hexdigest(),
            "result_layer": HOST_LAYER,
        })

    logit_cols = ["round", "source_index", "source_class"] + \
                 ["logit_%02d" % k for k in range(N_CLASSES)] + \
                 ["raw24_pred_pass1", "raw24_pred_pass2"]
    with open(os.path.join(args.out_dir, "raw24_logits.tsv"), "w", encoding="utf-8",
              newline="") as f:
        f.write("\t".join(logit_cols) + "\n")
        for r in sorted(logit_rows, key=lambda r: (r["round"], r["source_index"])):
            f.write("\t".join(str(r[c]) for c in logit_cols) + "\n")

    res_cols = ["round", "source_index", "source_class", "modulation", "baseline_pred",
                "raw24_pred_pass1", "raw24_pred_pass2", "baseline_agreement",
                "label_correct", "finite", "repeat_argmax_deterministic",
                "repeat_logits_byte_identical", "top1_logit", "top2_logit", "margin",
                "payload_training_residual", "payload_training_corr",
                "wide_linear_enabled", "raw_rx_sha256", "model_input_sha256",
                "result_layer"]
    with open(os.path.join(args.out_dir, "per_sample_results.tsv"), "w",
              encoding="utf-8", newline="") as f:
        f.write("\t".join(res_cols) + "\n")
        for r in sorted(result_rows, key=lambda r: (r["round"], r["source_index"])):
            f.write("\t".join(str(r[c]) for c in res_cols) + "\n")

    n = len(result_rows)
    n_agree = sum(r["baseline_agreement"] for r in result_rows)
    n_correct = sum(r["label_correct"] for r in result_rows)
    n_finite = sum(r["finite"] for r in result_rows)
    n_repeat_argmax = sum(r["repeat_argmax_deterministic"] for r in result_rows)
    n_repeat_byte = sum(r["repeat_logits_byte_identical"] for r in result_rows)

    summary = {
        "task_id": "fix10class24-dualsdr-repeat3-audit1",
        "phase": "C_host_inference",
        "result_layer": HOST_LAYER,
        "frozen_model_json_sha": FROZEN_MODEL_JSON_SHA,
        "frozen_model_raw_sha": FROZEN_MODEL_RAW_SHA,
        "sample_count": n,
        "rounds": rounds,
        "baseline_agreement": "%d/%d" % (n_agree, n),
        "label_correct": "%d/%d" % (n_correct, n),
        "finite": "%d/%d" % (n_finite, n),
        "repeat_argmax_deterministic": "%d/%d" % (n_repeat_argmax, n),
        "repeat_logits_byte_identical": "%d/%d" % (n_repeat_byte, n),
        "production_gate_modified": 0,
        "diagnostic_gate_bypass": 1,
        "merge_marker": "HYBRID_BOARD_GATED_PLUS_HOST_FORCED",
        "note": ("Host BF16 inference on gate-rejected samples is a DIAGNOSTIC "
                 "bypass (residual gate only); it is not a board NPU measurement "
                 "and is not a production gate change."),
    }
    with open(os.path.join(args.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")

    print("CLASSIFY_OK samples=%d baseline_agreement=%d/%d label_correct=%d/%d "
          "finite=%d/%d repeat_argmax=%d/%d repeat_logits_byte=%d/%d layer=%s" %
          (n, n_agree, n, n_correct, n, n_finite, n, n_repeat_argmax, n,
           n_repeat_byte, n, HOST_LAYER))
    return 0


if __name__ == "__main__":
    sys.exit(main())
