#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
four_way_oqpsk_scalar_wl.py -- fix10class24-scalarwl-4way (task 39e5) offline
four-way comparison: scalar / wide-linear  x  BF16 (board) / mixed-precision (Windows).

The board runner (iq_rf_loopback_24class_bf16_scalarwl_diag.hpp) performs ONE real
single-SDR capture of OQPSK(source_index=11500), recovers it with the SAME production
recovery core, exports BOTH model inputs (scalar + wide-linear), and infers the current
BF16 model on the board NPU -- producing the BF16 pair plus a manifest.  This script
completes the four-way table on the Windows host with the OLD mixed-precision model
(model_rml23/model_24class_ZG, 24-class source label order, INT8 body + BF16 head):

  1. `--phase mixed-precision`  run icraft-run.exe --backends Host on
     model_input_scalar_f32le.bin and model_input_wl_f32le.bin (the SAME two inputs the
     board exported), writing logits_scalar_mixed.bin / logits_wl_mixed.bin (24 x f32
     little-endian each) + mixed_precision_manifest.json.  Fail-closed on the frozen
     mixed-model SHA and on the exported-input SHA recorded in the board manifest.

  2. `--phase four-way`  combine the board BF16 pair (from
     scalarwl_diag_manifest.json) with the mixed pair into a 2x2 argmax/agreement table
     (scalar/WL x BF16/mixed) + four_way_report.json.  This is a MEASUREMENT -- the
     report surfaces the four-way facts; it never decides the final modification.

The 0.100 gate, production behaviour, the recovery core and both models are untouched.
No result here is a "board accuracy", and no conclusion is an RF_PASS.

Usage (on the Windows host, after the board run produced its out-dir):
  python scripts/four_way_oqpsk_scalar_wl.py --phase mixed-precision \
      --out-dir DIR --icraft-run /path/to/icraft-run.exe [--model-dir model_rml23]
  python scripts/four_way_oqpsk_scalar_wl.py --phase four-way --out-dir DIR

  # self-test (pure aggregation/math, no board, no icraft-run, no model):
  python scripts/four_way_oqpsk_scalar_wl.py --self-test
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

# ----------------------------------------------------------------------------
# constants (frozen contract values)
# ----------------------------------------------------------------------------
NETWORK_NAME = "model_24class"
EXPECT_CLASS_COUNT = 24
EXPECT_INPUT_BYTES = 2 * 1024 * 4  # [2,1024] fp32 = 8192 bytes

# Frozen 24-class source label order (identical to rml24::kLabelOrder24 and the
# mixed-precision SOURCE_LABEL_ORDER_24).  index 23 == OQPSK (the measured sample).
LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
)

# The OLD mixed-precision model (frozen; identity is fail-closed).
MIXED_MODEL_DIR = "model_rml23"
MIXED_MODEL_JSON_NAME = "model_24class_ZG.json"
MIXED_MODEL_RAW_NAME = "model_24class_ZG.raw"
MIXED_MODEL_JSON_SHA256 = (
    "d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d"
)
MIXED_MODEL_RAW_SHA256 = (
    "2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba"
)

# Board-runner exports (out-dir files).
BOARD_MANIFEST_NAME = "scalarwl_diag_manifest.json"
INPUT_SCALAR_NAME = "model_input_scalar_f32le.bin"
INPUT_WL_NAME = "model_input_wl_f32le.bin"
BF16_LOGITS_SCALAR_NAME = "logits_scalar_bf16.bin"
BF16_LOGITS_WL_NAME = "logits_wl_bf16.bin"

# This script's outputs (out-dir files).
MIXED_LOGITS_SCALAR_NAME = "logits_scalar_mixed.bin"
MIXED_LOGITS_WL_NAME = "logits_wl_mixed.bin"
MIXED_MANIFEST_NAME = "mixed_precision_manifest.json"
FOUR_WAY_REPORT_NAME = "four_way_report.json"


# ----------------------------------------------------------------------------
# small helpers
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
    # The C++ manifest writes doubles/floats via ostream (os << v), which emits
    # lowercase `nan` / `inf` / `-inf`; json.loads rejects those spellings.
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


def read_f32le(path, expected_count, what):
    if not os.path.isfile(path):
        fail("%s not found: %s" % (what, path))
    with open(path, "rb") as f:
        raw = f.read()
    if len(raw) != expected_count * 4:
        fail("%s is %d bytes (want %d x f32 = %d bytes)" %
             (path, len(raw), expected_count, expected_count * 4))
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


# ----------------------------------------------------------------------------
# pure four-way math (shared by phase four-way + self-test)
# ----------------------------------------------------------------------------
def make_cell(logits, name):
    a = np.asarray(logits, dtype=np.float64)
    if a.size != EXPECT_CLASS_COUNT:
        raise ValueError("%s has %d logits (want %d)" % (name, a.size, EXPECT_CLASS_COUNT))
    finite = bool(np.all(np.isfinite(a)))
    if finite:
        argmax = int(np.argmax(a))
        label = LABEL_ORDER_24[argmax] if 0 <= argmax < EXPECT_CLASS_COUNT else ""
        top1 = float(a[argmax])
        order = np.argsort(a)[::-1]
        top2 = float(a[order[1]]) if order.size > 1 else float("nan")
        margin = top1 - top2
    else:
        argmax = -1
        label = ""
        top1 = float("nan")
        top2 = float("nan")
        margin = float("nan")
    return {
        "name": name,
        "argmax": argmax,
        "label": label,
        "finite": finite,
        "top1_logit": top1,
        "top2_logit": top2,
        "margin": margin,
        "logits": [float(x) for x in a],
    }


def _agree(a, b):
    return bool(a["finite"] and b["finite"] and a["argmax"] == b["argmax"])


def build_four_way(manifest, bf16_scalar_logits, bf16_wl_logits,
                   mixed_scalar_logits, mixed_wl_logits):
    sc = int(manifest.get("source_class", -1))
    source_label = manifest.get("source_label", "") or (
        LABEL_ORDER_24[sc] if 0 <= sc < EXPECT_CLASS_COUNT else "")
    baseline_pred = int(manifest.get("baseline_pred", -1))

    cells = {
        "scalar_bf16": make_cell(bf16_scalar_logits, "scalar_bf16"),
        "wl_bf16": make_cell(bf16_wl_logits, "wl_bf16"),
        "scalar_mixed": make_cell(mixed_scalar_logits, "scalar_mixed"),
        "wl_mixed": make_cell(mixed_wl_logits, "wl_mixed"),
    }
    for c in cells.values():
        c["label_correct"] = 1 if (c["finite"] and c["argmax"] == sc) else 0
        c["baseline_agreement"] = 1 if (c["finite"] and c["argmax"] == baseline_pred) else 0

    agreement = {
        "scalar_bf16_mixed": _agree(cells["scalar_bf16"], cells["scalar_mixed"]),
        "wl_bf16_mixed": _agree(cells["wl_bf16"], cells["wl_mixed"]),
        "bf16_scalar_wl": _agree(cells["scalar_bf16"], cells["wl_bf16"]),
        "mixed_scalar_wl": _agree(cells["scalar_mixed"], cells["wl_mixed"]),
        "all_four": all(c["finite"] for c in cells.values()) and
                    len({cells[k]["argmax"] for k in cells}) == 1,
    }

    report = {
        "task_id": "fix10class24-scalarwl-4way",
        "source_index": int(manifest.get("source_index", -1)),
        "source_class": sc,
        "source_label": source_label,
        "modulation": manifest.get("modulation", ""),
        "snr_db": manifest.get("snr_db", ""),
        "split_role": manifest.get("split_role", ""),
        "baseline_pred": baseline_pred,
        "fidelity_verdict": manifest.get("fidelity_verdict", ""),
        "recovery_valid": bool(manifest.get("recovery_valid", False)),
        "payload_training_residual": manifest.get("payload_training_residual", ""),
        "wide_linear_enabled": bool(manifest.get("wide_linear_enabled", False)),
        "wl_recomputed": manifest.get("wl_recomputed", ""),
        "inputs_identical": manifest.get("inputs_identical", ""),
        "cells": cells,
        "agreement": agreement,
    }
    return report


# ----------------------------------------------------------------------------
# mixed-precision phase
# ----------------------------------------------------------------------------
def verify_mixed_model_identity(model_dir):
    model_json = Path(model_dir) / MIXED_MODEL_JSON_NAME
    model_raw = Path(model_dir) / MIXED_MODEL_RAW_NAME
    if not model_json.is_file() or not model_raw.is_file():
        fail("mixed-precision model json/raw not found under %s" % model_dir)
    if sha256_of(str(model_json)) != MIXED_MODEL_JSON_SHA256:
        fail("mixed model json SHA mismatch (not the frozen mixed-precision model): %s"
             % model_json)
    if sha256_of(str(model_raw)) != MIXED_MODEL_RAW_SHA256:
        fail("mixed model raw SHA mismatch (not the frozen mixed-precision model): %s"
             % model_raw)
    return str(model_json), str(model_raw)


def verify_exported_inputs(out_dir, manifest):
    scalar_path = os.path.join(out_dir, INPUT_SCALAR_NAME)
    wl_path = os.path.join(out_dir, INPUT_WL_NAME)
    for p in (scalar_path, wl_path):
        if not os.path.isfile(p):
            fail("model input not found: %s" % p)
        if os.path.getsize(p) != EXPECT_INPUT_BYTES:
            fail("%s size != %d bytes: %s" % (p, EXPECT_INPUT_BYTES, p))
    s_sha = sha256_of(scalar_path)
    w_sha = sha256_of(wl_path)
    m_s = manifest.get("input_scalar_sha256", "")
    m_w = manifest.get("input_wl_sha256", "")
    if m_s and s_sha != m_s:
        fail("scalar input SHA mismatch: file=%s manifest=%s" % (s_sha, m_s))
    if m_w and w_sha != m_w:
        fail("wide-linear input SHA mismatch: file=%s manifest=%s" % (w_sha, m_w))
    return scalar_path, wl_path, s_sha, w_sha


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
        fail("icraft-run exit %d: %s" %
             (proc.returncode, proc.stderr.decode("utf-8", "replace")[-2000:]))
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


def _mixed_one_input(icraft_run, model_json, model_raw, input_bin, logits_out_path,
                     input_sha):
    passes = classify_one_sample(icraft_run, model_json, model_raw, input_bin)
    p1, p2 = passes[0], passes[1]
    with open(logits_out_path, "wb") as f:
        f.write(p1["raw"])
    return {
        "input_sha256": input_sha,
        "logits_sha256": hashlib.sha256(p1["raw"]).hexdigest(),
        "argmax_pass1": p1["argmax"],
        "argmax_pass2": p2["argmax"],
        "label_pass1": LABEL_ORDER_24[p1["argmax"]] if 0 <= p1["argmax"] < EXPECT_CLASS_COUNT else "",
        "finite": bool(p1["finite"] and p2["finite"]),
        "repeat_argmax_deterministic": 1 if p1["argmax"] == p2["argmax"] else 0,
        "repeat_logits_byte_identical": 1 if p1["raw"] == p2["raw"] else 0,
    }


def phase_mixed_precision(args):
    out_dir = os.path.abspath(args.out_dir)
    board_manifest_path = os.path.join(out_dir, BOARD_MANIFEST_NAME)
    if not os.path.isfile(board_manifest_path):
        fail("board manifest not found: %s (run the board first)" % board_manifest_path)
    manifest = load_json_nan_tolerant(board_manifest_path)

    if not args.icraft_run:
        fail("--icraft-run is required for --phase mixed-precision")
    model_dir = os.path.abspath(args.model_dir) if args.model_dir else MIXED_MODEL_DIR
    model_json, model_raw = verify_mixed_model_identity(model_dir)
    scalar_path, wl_path, s_sha, w_sha = verify_exported_inputs(out_dir, manifest)

    rec = {}
    rec["scalar"] = _mixed_one_input(args.icraft_run, model_json, model_raw,
                                     scalar_path,
                                     os.path.join(out_dir, MIXED_LOGITS_SCALAR_NAME),
                                     s_sha)
    rec["wl"] = _mixed_one_input(args.icraft_run, model_json, model_raw,
                                 wl_path,
                                 os.path.join(out_dir, MIXED_LOGITS_WL_NAME),
                                 w_sha)

    mmanifest = {
        "task_id": "fix10class24-scalarwl-4way",
        "phase": "mixed-precision",
        "network_name": NETWORK_NAME,
        "model_json_sha256": MIXED_MODEL_JSON_SHA256,
        "model_raw_sha256": MIXED_MODEL_RAW_SHA256,
        "model_dir": model_dir,
        "inputs_identical": manifest.get("inputs_identical", ""),
        "scalar": rec["scalar"],
        "wl": rec["wl"],
    }
    with open(os.path.join(out_dir, MIXED_MANIFEST_NAME), "w", encoding="utf-8") as f:
        json.dump(mmanifest, f, indent=2, sort_keys=True)
        f.write("\n")

    print("MIXED_PRECISION_OK scalar_argmax=%d(%s) wl_argmax=%d(%s) "
          "scalar_deterministic=%d wl_deterministic=%d manifest=%s" %
          (rec["scalar"]["argmax_pass1"], rec["scalar"]["label_pass1"],
           rec["wl"]["argmax_pass1"], rec["wl"]["label_pass1"],
           rec["scalar"]["repeat_argmax_deterministic"],
           rec["wl"]["repeat_argmax_deterministic"],
           os.path.join(out_dir, MIXED_MANIFEST_NAME)))
    return 0


# ----------------------------------------------------------------------------
# four-way phase
# ----------------------------------------------------------------------------
def phase_four_way(args):
    out_dir = os.path.abspath(args.out_dir)
    board_manifest_path = os.path.join(out_dir, BOARD_MANIFEST_NAME)
    if not os.path.isfile(board_manifest_path):
        fail("board manifest not found: %s" % board_manifest_path)
    manifest = load_json_nan_tolerant(board_manifest_path)

    # BF16 pair: authoritative vectors live in the manifest; cross-check the exported
    # .bin files against them fail-closed (catches tampering / partial export).
    bf16_scalar = np.asarray(manifest.get("bf16_logits_scalar", []), dtype=np.float64)
    bf16_wl = np.asarray(manifest.get("bf16_logits_wl", []), dtype=np.float64)
    if bf16_scalar.size != EXPECT_CLASS_COUNT or bf16_wl.size != EXPECT_CLASS_COUNT:
        fail("board manifest missing a 24-dim BF16 logit vector")
    bf16_scalar_bin = read_f32le(os.path.join(out_dir, BF16_LOGITS_SCALAR_NAME),
                                 EXPECT_CLASS_COUNT, "BF16 scalar logits bin")
    bf16_wl_bin = read_f32le(os.path.join(out_dir, BF16_LOGITS_WL_NAME),
                             EXPECT_CLASS_COUNT, "BF16 wide-linear logits bin")
    if not np.array_equal(bf16_scalar, bf16_scalar_bin):
        fail("BF16 scalar logits: manifest vs bin disagree")
    if not np.array_equal(bf16_wl, bf16_wl_bin):
        fail("BF16 wide-linear logits: manifest vs bin disagree")

    # mixed pair: produced by --phase mixed-precision.
    mixed_scalar = read_f32le(os.path.join(out_dir, MIXED_LOGITS_SCALAR_NAME),
                              EXPECT_CLASS_COUNT, "mixed scalar logits bin")
    mixed_wl = read_f32le(os.path.join(out_dir, MIXED_LOGITS_WL_NAME),
                          EXPECT_CLASS_COUNT, "mixed wide-linear logits bin")

    mixed_manifest_path = os.path.join(out_dir, MIXED_MANIFEST_NAME)
    if os.path.isfile(mixed_manifest_path):
        mm = load_json_nan_tolerant(mixed_manifest_path)
    else:
        mm = None

    report = build_four_way(manifest, bf16_scalar, bf16_wl, mixed_scalar, mixed_wl)
    report["mixed_precision_manifest"] = mm

    with open(os.path.join(out_dir, FOUR_WAY_REPORT_NAME), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")

    ag = report["agreement"]
    print("FOUR_WAY_OK source=%s(%d) scalar_bf16=%s wl_bf16=%s scalar_mixed=%s "
          "wl_mixed=%s | scalar_bf16_mixed=%d wl_bf16_mixed=%d bf16_scalar_wl=%d "
          "mixed_scalar_wl=%d all_four=%d report=%s" %
          (report["source_label"], report["source_class"],
           report["cells"]["scalar_bf16"]["label"], report["cells"]["wl_bf16"]["label"],
           report["cells"]["scalar_mixed"]["label"], report["cells"]["wl_mixed"]["label"],
           int(ag["scalar_bf16_mixed"]), int(ag["wl_bf16_mixed"]),
           int(ag["bf16_scalar_wl"]), int(ag["mixed_scalar_wl"]),
           int(ag["all_four"]), os.path.join(out_dir, FOUR_WAY_REPORT_NAME)))
    return 0


# ----------------------------------------------------------------------------
# self-test (pure math / identity, no board, no icraft-run, no model)
# ----------------------------------------------------------------------------
def _logits(argmax):
    v = np.full(EXPECT_CLASS_COUNT, -10.0)
    v[argmax] = 5.0
    v[(argmax + 1) % EXPECT_CLASS_COUNT] = 3.0
    return v.tolist()


def _base_manifest():
    return {
        "source_index": 11500,
        "source_class": 23,
        "source_label": "OQPSK",
        "modulation": "OQPSK",
        "snr_db": 18.0,
        "split_role": "holdout",
        "baseline_pred": 23,
        "fidelity_verdict": "RF_PRESERVES_IQ",
        "recovery_valid": True,
        "payload_training_residual": 0.05,
        "wide_linear_enabled": False,
        "wl_recomputed": True,
        "inputs_identical": False,
    }


def self_test():
    checks = 0
    failures = []

    def check(cond, what):
        nonlocal checks
        checks += 1
        if not cond:
            failures.append(what)

    # label order identity
    check(len(LABEL_ORDER_24) == 24, "label order length == 24")
    check(LABEL_ORDER_24[0] == "OOK" and LABEL_ORDER_24[23] == "OQPSK",
          "label order endpoints OOK/OQPSK")
    check(len(set(LABEL_ORDER_24)) == 24, "label order has no duplicates")

    # mixed-model SHA constants (frozen, fail-closed identity)
    check(len(MIXED_MODEL_JSON_SHA256) == 64 and
          len(MIXED_MODEL_RAW_SHA256) == 64, "mixed model SHA constants are 64 hex chars")

    # ---- scenario A: all four point to OQPSK(23) -> all correct, all agree ----
    m = _base_manifest()
    r = build_four_way(m, _logits(23), _logits(23), _logits(23), _logits(23))
    for k in r["cells"]:
        c = r["cells"][k]
        check(c["argmax"] == 23 and c["label"] == "OQPSK", "A: %s argmax=23 OQPSK" % k)
        check(c["label_correct"] == 1, "A: %s label_correct" % k)
        check(c["baseline_agreement"] == 1, "A: %s baseline_agreement" % k)
    check(r["agreement"]["all_four"] is True, "A: all_four agree")
    check(r["agreement"]["scalar_bf16_mixed"] is True, "A: scalar_bf16_mixed agree")
    check(r["agreement"]["bf16_scalar_wl"] is True, "A: bf16_scalar_wl agree")

    # ---- scenario B: mixed-WL disagrees (points at 32PSK=7) ----
    r = build_four_way(m, _logits(23), _logits(23), _logits(23), _logits(7))
    check(r["cells"]["wl_mixed"]["label"] == "32PSK", "B: wl_mixed label 32PSK")
    check(r["agreement"]["scalar_bf16_mixed"] is True, "B: scalar_bf16_mixed agree")
    check(r["agreement"]["wl_bf16_mixed"] is False, "B: wl_bf16_mixed disagree")
    check(r["agreement"]["mixed_scalar_wl"] is False, "B: mixed_scalar_wl disagree")
    check(r["agreement"]["bf16_scalar_wl"] is True, "B: bf16_scalar_wl agree")
    check(r["agreement"]["all_four"] is False, "B: all_four disagree")

    # ---- scenario C: non-finite cell is never counted as agreement ----
    bad = [float("nan")] * EXPECT_CLASS_COUNT
    r = build_four_way(m, _logits(23), _logits(23), bad, bad)
    check(r["cells"]["scalar_mixed"]["finite"] is False, "C: non-finite flagged")
    check(r["agreement"]["scalar_bf16_mixed"] is False, "C: non-finite never agrees")
    check(r["agreement"]["all_four"] is False, "C: non-finite all_four false")

    # ---- scenario D: wrong-but-consistent (all point to 4ASK=1) ----
    m2 = _base_manifest()
    r = build_four_way(m2, _logits(1), _logits(1), _logits(1), _logits(1))
    check(all(r["cells"][k]["argmax"] == 1 for k in r["cells"]), "D: all argmax=1")
    check(all(r["cells"][k]["label_correct"] == 0 for k in r["cells"]),
          "D: all label_correct=0 (wrong class, still agree)")
    check(r["agreement"]["all_four"] is True, "D: all_four agree despite wrong class")

    # ---- scenario E: input cross-check helper (synthetic out-dir) ----
    with tempfile.TemporaryDirectory() as td:
        scalar_path = os.path.join(td, INPUT_SCALAR_NAME)
        wl_path = os.path.join(td, INPUT_WL_NAME)
        with open(scalar_path, "wb") as f:
            f.write(b"\x00" * EXPECT_INPUT_BYTES)
        with open(wl_path, "wb") as f:
            f.write(b"\x01" * EXPECT_INPUT_BYTES)
        manifest = {
            "input_scalar_sha256": sha256_of(scalar_path),
            "input_wl_sha256": sha256_of(wl_path),
        }
        sp, wp, s_sha, w_sha = verify_exported_inputs(td, manifest)
        check(sp == scalar_path and wp == wl_path, "E: cross-check paths returned")
        check(s_sha == manifest["input_scalar_sha256"], "E: scalar SHA matches")
        # tampered manifest must fail-closed
        bad_manifest = dict(manifest, input_scalar_sha256="0" * 64)
        try:
            verify_exported_inputs(td, bad_manifest)
            check(False, "E: tampered scalar SHA must fail-closed")
        except SystemExit:
            check(True, "E: tampered scalar SHA fail-closed (SystemExit)")

    # ---- scenario F: read_f32le round-trip + size fail-closed ----
    with tempfile.TemporaryDirectory() as td:
        arr = np.arange(EXPECT_CLASS_COUNT, dtype=np.float64) * 0.5
        p = os.path.join(td, "logits.bin")
        with open(p, "wb") as f:
            f.write(arr.astype("<f4").tobytes())
        got = read_f32le(p, EXPECT_CLASS_COUNT, "test logits")
        check(np.allclose(got, arr), "F: read_f32le round-trip")
        with open(p, "wb") as f:
            f.write(b"\x00" * (EXPECT_CLASS_COUNT * 4 + 4))
        try:
            read_f32le(p, EXPECT_CLASS_COUNT, "test logits")
            check(False, "F: oversized bin must fail-closed")
        except SystemExit:
            check(True, "F: oversized bin fail-closed (SystemExit)")

    if failures:
        for f in failures:
            sys.stderr.write("SELF-TEST FAIL: %s\n" % f)
        print("SELF_TEST_RESULT checks=%d failures=%d" % (checks, len(failures)))
        return 1
    print("SELF_TEST_RESULT checks=%d failures=0" % checks)
    return 0


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="fix10class24-scalarwl-4way four-way comparison")
    ap.add_argument("--self-test", action="store_true",
                    help="pure four-way math / identity self-test (no board, no icraft-run)")
    ap.add_argument("--phase", choices=["mixed-precision", "four-way"])
    ap.add_argument("--out-dir", help="runner --out-dir (board manifest + exported inputs)")
    ap.add_argument("--icraft-run", help="path to icraft-run.exe (Host backend)")
    ap.add_argument("--model-dir", help="dir holding model_24class_ZG.json/.raw "
                                        "(default model_rml23)")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if args.phase in ("mixed-precision", "four-way"):
        if not args.out_dir:
            ap.error("--phase %s requires --out-dir" % args.phase)
        if args.phase == "mixed-precision":
            return phase_mixed_precision(args)
        return phase_four_way(args)

    ap.error("pass --self-test or --phase mixed-precision|four-way")


if __name__ == "__main__":
    sys.exit(main())
