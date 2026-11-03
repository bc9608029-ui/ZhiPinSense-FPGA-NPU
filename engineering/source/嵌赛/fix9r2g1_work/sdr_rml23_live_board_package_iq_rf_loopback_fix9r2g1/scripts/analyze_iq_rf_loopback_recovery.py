#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_iq_rf_loopback_recovery.py -- Route F fix9r Task A: root-cause analyzer for
the fix9 same-machine Pluto RF loopback.

It parses the fix9 `--phase=iq-rf-loopback-23class` stdout log (the IQ_RF_LOOPBACK*
lines), computes the per-file RF gain/phase/CFO/phase-drift/tensor statistics, and
selects a root cause FROM THE EVIDENCE (it never assumes the global phase is the
only cause).  When the evidence is insufficient or no anomaly is present it returns
NOT_PROVEN.

Candidate verdicts (evidence-selected, never hardcoded):
    PER_FILE_PHASE_UNRECOVERED    per-file RF phase varies beyond one global phase
    PER_FILE_GAIN_UNRECOVERED     per-file RF gain magnitude varies beyond one gain
    CFO_PHASE_DRIFT               carrier offset / intra-file phase drift too large
    SRO_MISALIGNMENT              (same-machine SRO ~ 0; flagged only on explicit clue)
    D2_SCALE_ORDER_ERROR          model-domain gain order/scale wrong (tensor residual)
    D2_DC_RESTORE_ORDER_ERROR     model-domain DC restore order wrong (tensor residual)
    IQ_SWAP_OR_CONJUGATE          IQ swap / conjugate (corr_swap/corr_conj present)
    MODEL_DOMAIN_RECOVERY_NOT_PROVEN   RF preserved but model domain still wrong
    NOT_PROVEN                    no evidence / no anomaly (nominal)

Optional --baseline <tsv> (Task B/F): pairs every RF file with its exact baseline
prediction and computes prediction_agreement / accuracy_delta_pp for the §9 gate.

Pure standard library (no numpy) -- runs with `python -I`.
"""

import argparse
import json
import math
import statistics
import sys

# ---------------------------------------------------------------------------
# Thresholds (documented; tunable).  Same-machine Pluto => CFO ~ 0, SRO ~ 0.
# ---------------------------------------------------------------------------
K_RF_CORR_PRESERVED = 0.9      # below this the waveform itself is not recovered
K_PHASE_STD_DEG = 30.0         # circular std above this -> per-file phase problem
K_GAIN_REL_STD = 0.25          # (std/median) of gain magnitude above -> gain problem
K_CFO_HZ = 500.0               # |cfo_hz| above -> CFO problem
K_DRIFT_DEG = 15.0             # |phase_drift_deg| above -> drift problem
K_TENSOR_NMSE = 0.10           # tensor nmse above -> model-domain residual (D2 order)
K_TENSOR_CORR = 0.95           # tensor corr below -> model-domain residual


# ---------------------------------------------------------------------------
# Small math helpers
# ---------------------------------------------------------------------------
def wrap_deg(x):
    return (x + 180.0) % 360.0 - 180.0


def circular_mean_deg(phases_deg):
    """Circular mean of angles in degrees."""
    if not phases_deg:
        return None
    sx = sy = 0.0
    for p in phases_deg:
        r = math.radians(p)
        sx += math.cos(r)
        sy += math.sin(r)
    return math.degrees(math.atan2(sy, sx)) % 360.0


def circular_std_deg(phases_deg):
    """Circular std in degrees (sqrt(-2 ln R)); inf for a uniform circle."""
    if not phases_deg:
        return None
    sx = sy = 0.0
    for p in phases_deg:
        r = math.radians(p)
        sx += math.cos(r)
        sy += math.sin(r)
    R = math.hypot(sx, sy) / len(phases_deg)
    R = max(0.0, min(1.0 - 1e-12, R))
    return math.degrees(math.sqrt(-2.0 * math.log(R)))


def db_to_mag(db):
    return 10.0 ** (db / 20.0)


def rel_std(vals):
    if not vals:
        return None
    med = statistics.median(vals)
    if med == 0.0:
        return 0.0 if all(v == 0.0 for v in vals) else float("inf")
    return statistics.pstdev(vals) / abs(med)


def _f(tok, key, default=None):
    """Parse a float token value; returns default when absent/malformed."""
    v = tok.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError:
        return default


def _i(tok, key, default=None):
    v = tok.get(key)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Log parsing
# ---------------------------------------------------------------------------
def tokenize(line):
    """Split a `key=value ...` line into an ordered dict (values are space-free)."""
    d = {}
    for piece in line.split():
        if "=" in piece:
            k, _, v = piece.partition("=")
            if k:
                d[k] = v
    return d


def parse_log(text):
    """Parse a fix9 run log into {calibration, files[per-file dicts in order]}."""
    calibration = {}
    files = []
    by_name = {}

    def file_rec(name):
        if name not in by_name:
            rec = {"name": name}
            by_name[name] = rec
            files.append(rec)
        return by_name[name]

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("IQ_RF_LOOPBACK_CALIBRATION "):
            calibration = tokenize(line)
            continue
        if line.startswith("IQ_RF_LOOPBACK_WINDOW "):
            t = tokenize(line)
            if "file" in t:
                rec = file_rec(t["file"])
                rec["tensor_corr"] = _f(t, "corr")
                rec["tensor_nmse"] = _f(t, "nmse")
                rec["tensor_gain_db"] = _f(t, "gain_db")
                rec["sha_equal"] = _i(t, "sha_equal")
            continue
        # The D2 restore line carries source_index (the manifest index, unique
        # per sample) -- the key the exact-baseline TSV pairs on.  NB the
        # prediction line's `source=` is source_class (raw 24 class), NOT this.
        if line.startswith("IQ_RF_LOOPBACK_D2_RESTORE "):
            t = tokenize(line)
            if "file" in t and "source_index" in t:
                rec = file_rec(t["file"])
                rec["source_index"] = _i(t, "source_index")
            continue
        # The per-file fidelity line and the per-file prediction line both start
        # with a bare "IQ_RF_LOOPBACK " (not "..._").  Dispatch on their keys.
        if line.startswith("IQ_RF_LOOPBACK ") and "file=" in line:
            t = tokenize(line)
            if "file" not in t:
                continue
            name = t["file"]
            if "fidelity" in t:
                rec = file_rec(name)
                rec["rf_verdict"] = t["fidelity"]
                rec["rf_gain_db"] = _f(t, "gain_db")
                rec["rf_phase_deg"] = _f(t, "phase_deg")
                rec["rf_corr"] = _f(t, "corr")
                rec["rf_peak_corr"] = _f(t, "peak_corr")
                rec["rf_normalized_residual"] = _f(t, "normalized_residual")
                rec["rf_cfo_hz"] = _f(t, "cfo_hz")
                rec["rf_phase_drift_deg"] = _f(t, "phase_drift_deg")
                rec["rf_snr_db"] = _f(t, "snr_db")
                rec["rf_rms_tx"] = _f(t, "rms_tx")
                rec["rf_rms_rx"] = _f(t, "rms_rx")
                # forward-compatible: fix9r logs may print swap/conjugate probes
                rec["corr_swap"] = _f(t, "corr_swap")
                rec["corr_conj"] = _f(t, "corr_conj")
            elif "frames" in t and ("correct" in t):
                rec = file_rec(name)
                rec["pred_correct"] = _i(t, "correct")
                rec["pred_deployed"] = _i(t, "deployed")
                rec["pred_source"] = _i(t, "source")
                rec["pred_raw24"] = _i(t, "raw24_pred")
                rec["pred_merged23"] = _i(t, "merged23_pred")
            continue

    return {"calibration": calibration, "files": files}


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
def analyze(data):
    files = data["files"]
    cal = data["calibration"]

    phases = [f["rf_phase_deg"] for f in files
              if f.get("rf_phase_deg") is not None]
    gains = [db_to_mag(f["rf_gain_db"]) for f in files
             if f.get("rf_gain_db") is not None]
    cfos = [f["rf_cfo_hz"] for f in files if f.get("rf_cfo_hz") is not None]
    drifts = [f["rf_phase_drift_deg"] for f in files
              if f.get("rf_phase_drift_deg") is not None]
    rf_corrs = [f["rf_corr"] for f in files if f.get("rf_corr") is not None]
    tens_nmse = [f["tensor_nmse"] for f in files
                 if f.get("tensor_nmse") is not None]
    tens_corr = [f["tensor_corr"] for f in files
                 if f.get("tensor_corr") is not None]

    # phase change across consecutive TX rebuilds (each file re-keys the TX LO).
    phase_deltas = [wrap_deg(phases[i] - phases[i - 1])
                    for i in range(1, len(phases))]

    stats = {
        "n_files": len(files),
        "n_rf_fidelity": len(rf_corrs),
        "n_tensor": len(tens_nmse),
        "phase_mean_deg": circular_mean_deg(phases),
        "phase_circular_std_deg": circular_std_deg(phases),
        "phase_min_deg": min(phases) if phases else None,
        "phase_max_deg": max(phases) if phases else None,
        "phase_rebuild_delta_mean_abs_deg":
            (sum(abs(d) for d in phase_deltas) / len(phase_deltas)
             if phase_deltas else None),
        "phase_rebuild_delta_max_abs_deg":
            (max(abs(d) for d in phase_deltas) if phase_deltas else None),
        "gain_mag_median": statistics.median(gains) if gains else None,
        "gain_mag_min": min(gains) if gains else None,
        "gain_mag_max": max(gains) if gains else None,
        "gain_mag_rel_std": rel_std(gains),
        "cfo_hz_min": min(cfos) if cfos else None,
        "cfo_hz_max": max(cfos) if cfos else None,
        "cfo_hz_max_abs": max(abs(c) for c in cfos) if cfos else None,
        "phase_drift_min_deg": min(drifts) if drifts else None,
        "phase_drift_max_deg": max(drifts) if drifts else None,
        "phase_drift_max_abs_deg": max(abs(d) for d in drifts) if drifts else None,
        "rf_corr_median": statistics.median(rf_corrs) if rf_corrs else None,
        "rf_corr_min": min(rf_corrs) if rf_corrs else None,
        "tensor_nmse_median": statistics.median(tens_nmse) if tens_nmse else None,
        "tensor_nmse_max": max(tens_nmse) if tens_nmse else None,
        "tensor_corr_median": statistics.median(tens_corr) if tens_corr else None,
        "tensor_corr_min": min(tens_corr) if tens_corr else None,
    }
    if cal:
        stats["global_gain_mag"] = _f(cal, "mag")
        stats["global_gain_phase_deg"] = _f(cal, "phase_deg")
        stats["global_gain_k_mag"] = _f(cal, "k_mag")
        stats["global_gain_k_phase_deg"] = _f(cal, "k_phase_deg")

    # prediction distribution
    pred_hist = {}
    for f in files:
        if f.get("pred_merged23") is not None:
            pred_hist[str(f["pred_merged23"])] = pred_hist.get(
                str(f["pred_merged23"]), 0) + 1
    stats["pred_merged23_histogram"] = pred_hist
    n_correct = sum(1 for f in files if f.get("pred_correct") == 1)
    n_scored = sum(1 for f in files if f.get("pred_correct") is not None)
    stats["n_scored"] = n_scored
    stats["n_correct"] = n_correct
    stats["accuracy"] = (n_correct / n_scored) if n_scored else None

    # ---- evidence + verdict (ordered; first hit wins) ----------------------
    evidence = []
    verdict = "NOT_PROVEN"
    nominal = False

    rf_med = stats["rf_corr_median"]
    phase_std = stats["phase_circular_std_deg"]
    gain_rel = stats["gain_mag_rel_std"]
    cfo_max = stats["cfo_hz_max_abs"]
    drift_max = stats["phase_drift_max_abs_deg"]
    nmse_med = stats["tensor_nmse_median"]
    tcorr_med = stats["tensor_corr_median"]

    # Verdict selection: most-specific diagnosable cause first.  IQ swap and
    # conjugate present as LOW normal correlation, so they must precede the
    # generic "corr below preserved" fallback (otherwise they are masked).
    swap_dominant = any(f.get("corr_swap") is not None and
                        f.get("rf_corr") is not None and
                        f["corr_swap"] > f["rf_corr"] for f in files)
    conj_dominant = any(f.get("corr_conj") is not None and
                        f.get("rf_corr") is not None and
                        f["corr_conj"] > f["rf_corr"] for f in files)

    if swap_dominant:
        evidence.append("iq_swap_dominant")
        verdict = "IQ_SWAP_OR_CONJUGATE"
    elif conj_dominant:
        evidence.append("conjugate_dominant")
        verdict = "IQ_SWAP_OR_CONJUGATE"
    elif cfo_max is not None and cfo_max > K_CFO_HZ:
        evidence.append("cfo_out_of_range")
        verdict = "CFO_PHASE_DRIFT"
    elif drift_max is not None and drift_max > K_DRIFT_DEG:
        evidence.append("phase_drift_out_of_range")
        verdict = "CFO_PHASE_DRIFT"
    # waveform-level: if the RF corr itself is poor, the problem is upstream of
    # the model domain (outside fix9r's recovery scope).
    elif rf_med is not None and rf_med < K_RF_CORR_PRESERVED:
        evidence.append("rf_corr_below_preserved")
        verdict = "NOT_PROVEN"
    elif phase_std is not None and phase_std > K_PHASE_STD_DEG:
        evidence.append("per_file_phase_spread")
        verdict = "PER_FILE_PHASE_UNRECOVERED"
    elif gain_rel is not None and gain_rel > K_GAIN_REL_STD:
        evidence.append("per_file_gain_spread")
        verdict = "PER_FILE_GAIN_UNRECOVERED"
    elif (nmse_med is not None and nmse_med > K_TENSOR_NMSE) or \
         (tcorr_med is not None and tcorr_med < K_TENSOR_CORR):
        evidence.append("tensor_domain_residual")
        verdict = "MODEL_DOMAIN_RECOVERY_NOT_PROVEN"
    else:
        nominal = True
        evidence.append("no_anomaly")
        verdict = "NOT_PROVEN"

    return {"stats": stats, "verdict": verdict, "evidence": evidence,
            "nominal": nominal, "per_file": files}


# ---------------------------------------------------------------------------
# Optional exact-baseline pairing (Task B output, reused by Task F)
# ---------------------------------------------------------------------------
def load_baseline(path):
    """Parse route_f_fix9r_exact_baseline.tsv -> {source_index: rec}.

    The baseline TSV columns are exactly the five build_route_f_fix9r_exact_baseline
    writes: source_index / original_sha256 / deployed_class / modulation /
    split_role.  `deployed_class` is the ground-truth label AND the model's known
    original-data prediction (99.34% accurate), so it serves as the baseline
    prediction the RF run is compared against.
    """
    out = {}
    with open(path, "r", encoding="utf-8") as fh:
        header = None
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            cols = line.split("\t")
            if header is None:
                header = cols
                continue
            if len(cols) != len(header):
                raise ValueError("baseline row width != header: %r" % cols)
            rec = dict(zip(header, cols))
            out[int(rec["source_index"])] = rec
    return out


def compare_baseline(data, baseline, baseline_accuracy=0.9934):
    """Pair RF files with exact-baseline ground truth; compute §9 agreement stats.

    The baseline's deployed_class is the model's original-data prediction (the
    model scores 99.34% on original data), so the §9 metrics are:
        prediction_agreement = P(rf merged23 pred == baseline deployed_class)
        rf_accuracy          = P(rf pred is correct)  (== same fraction, since the
                                log's `correct` is merged23 == fz.deployed_class)
        accuracy_delta_pp    = 100 * (rf_accuracy - baseline_accuracy)
    Pairing key is source_index (from IQ_RF_LOOPBACK_D2_RESTORE), NOT the
    prediction line's `source=` (which is source_class / raw 24 class).
    """
    n_pair = 0
    n_agree = 0
    rf_correct = 0
    rows = []
    for f in data["files"]:
        if f.get("pred_merged23") is None:
            continue
        sid = f.get("source_index")
        if sid is None or sid not in baseline:
            continue
        b_pred = int(baseline[sid].get("deployed_class"))
        rf_pred = int(f["pred_merged23"])
        rfc = 1 if f.get("pred_correct") == 1 else 0
        agree = 1 if rf_pred == b_pred else 0
        n_pair += 1
        n_agree += agree
        rf_correct += rfc
        rows.append({"source_index": sid,
                     "baseline_deployed_class": b_pred,
                     "rf_merged23_pred": rf_pred,
                     "agree": agree, "rf_correct": rfc})
    if n_pair == 0:
        return {"n_pair": 0}
    rf_accuracy = rf_correct / n_pair
    return {
        "n_pair": n_pair,
        "prediction_agreement": n_agree / n_pair,
        "baseline_accuracy": baseline_accuracy,
        "rf_accuracy": rf_accuracy,
        "accuracy_delta_pp": 100.0 * (rf_accuracy - baseline_accuracy),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Self-test (>=6 synthetic scenarios)
# ---------------------------------------------------------------------------
def _fid_line(name, gain_db, phase_deg, corr, cfo=0.0, drift=0.0,
              normalized_residual=0.01, swap=None, conj=None):
    extra = ""
    if swap is not None:
        extra += " corr_swap=%.4f" % swap
    if conj is not None:
        extra += " corr_conj=%.4f" % conj
    return ("IQ_RF_LOOPBACK file=%s fidelity=RF_PRESERVES_IQ "
            "gain_db=%.3f phase_deg=%.3f normalized_residual=%.4f corr=%.4f "
            "cfo_hz=%.3f phase_drift_deg=%.3f rms_tx=2048.0 rms_rx=34.0 "
            "snr_db=20.0%s" % (name, gain_db, phase_deg, normalized_residual,
                               corr, cfo, drift, extra))


def _win_line(name, tensor_corr, tensor_nmse, tensor_gain_db=0.0):
    return ("IQ_RF_LOOPBACK_WINDOW file=%s recovered_frames=4 delay_offset=0 "
            "corr=%.4f nmse=%.4f gain_db=%.3f sha_equal=0 aligned_sha=0 ref_sha=1"
            % (name, tensor_corr, tensor_nmse, tensor_gain_db))


def _pred_line(name, correct, deployed, merged):
    return ("IQ_RF_LOOPBACK file=%s frames=1 correct=%d deployed=%d source=%d "
            "raw24_pred=%d merged23_pred=%d"
            % (name, correct, deployed, deployed, merged, merged))


def _calib_line(mag=0.016876, phase=95.110):
    return ("IQ_RF_LOOPBACK_CALIBRATION calib_files=184 used=183 valid=1 "
            "mag=%.6f phase_deg=%.3f k_mag=%.6f k_phase_deg=%.3f"
            % (mag, phase, 1.0 / mag, -phase))


def _run_scenarios():
    """Return list of (name, log_text, expected_verdict)."""
    sc = []

    # 1. per-file random phase (uniform) -> PER_FILE_PHASE_UNRECOVERED
    phases = [0.0, 72.0, 144.0, 216.0, 288.0]
    log = [_calib_line()] + \
          [_fid_line("f%d" % i, -35.4, p, 0.99) for i, p in enumerate(phases)] + \
          [_win_line("f%d" % i, 0.95, 0.02) for i in range(len(phases))] + \
          [_pred_line("f%d" % i, 0, i % 23, (i * 7) % 23)
           for i in range(len(phases))]
    sc.append(("random_phase", "\n".join(log), "PER_FILE_PHASE_UNRECOVERED"))

    # 2. per-file random gain -> PER_FILE_GAIN_UNRECOVERED
    gains = [-10.0, -40.0, -25.0, -55.0, -15.0]
    log = [_calib_line()] + \
          [_fid_line("f%d" % i, g, 90.0, 0.99) for i, g in enumerate(gains)] + \
          [_win_line("f%d" % i, 0.95, 0.02) for i in range(len(gains))]
    sc.append(("random_gain", "\n".join(log), "PER_FILE_GAIN_UNRECOVERED"))

    # 3. large CFO -> CFO_PHASE_DRIFT
    log = [_calib_line()] + \
          [_fid_line("f%d" % i, -35.4, 90.0, 0.99, cfo=1200.0) for i in range(4)]
    sc.append(("large_cfo", "\n".join(log), "CFO_PHASE_DRIFT"))

    # 4. intra-file phase drift -> CFO_PHASE_DRIFT
    log = [_calib_line()] + \
          [_fid_line("f%d" % i, -35.4, 90.0, 0.99, drift=25.0) for i in range(4)]
    sc.append(("phase_drift", "\n".join(log), "CFO_PHASE_DRIFT"))

    # 5. stable RF but bad tensor (model-domain) -> MODEL_DOMAIN_RECOVERY_NOT_PROVEN
    log = [_calib_line()] + \
          [_fid_line("f%d" % i, -35.4, 90.0, 0.99) for i in range(4)] + \
          [_win_line("f%d" % i, 0.80, 0.20) for i in range(4)]
    sc.append(("stable_rf_bad_tensor", "\n".join(log),
               "MODEL_DOMAIN_RECOVERY_NOT_PROVEN"))

    # 6. IQ swap dominant -> IQ_SWAP_OR_CONJUGATE
    log = [_calib_line()] + \
          [_fid_line("f%d" % i, -35.4, 90.0, 0.60, swap=0.99) for i in range(4)]
    sc.append(("iq_swap", "\n".join(log), "IQ_SWAP_OR_CONJUGATE"))

    # 7. conjugate dominant -> IQ_SWAP_OR_CONJUGATE
    log = [_calib_line()] + \
          [_fid_line("f%d" % i, -35.4, 90.0, 0.60, conj=0.98) for i in range(4)]
    sc.append(("conjugate", "\n".join(log), "IQ_SWAP_OR_CONJUGATE"))

    # 8. healthy (nominal) -> NOT_PROVEN (nominal)
    log = [_calib_line()] + \
          [_fid_line("f%d" % i, -35.4, 90.0, 0.99) for i in range(4)] + \
          [_win_line("f%d" % i, 0.99, 0.005) for i in range(4)] + \
          [_pred_line("f%d" % i, 1, i % 23, i % 23) for i in range(4)]
    sc.append(("healthy", "\n".join(log), "NOT_PROVEN"))

    return sc


def _self_test_baseline():
    """Verify the exact-baseline pairing / §9 metric computation (Task B/F)."""
    # baseline keyed by source_index, deployed_class is the ground-truth prediction.
    baseline = {0: {"deployed_class": "0"},
                1: {"deployed_class": "1"},
                2: {"deployed_class": "2"}}
    # files: source_index from D2_RESTORE; merged23 pred correct for 0,1 wrong for 2.
    data = {"files": [
        {"source_index": 0, "pred_merged23": 0, "pred_correct": 1},
        {"source_index": 1, "pred_merged23": 1, "pred_correct": 1},
        {"source_index": 2, "pred_merged23": 5, "pred_correct": 0},
        {"source_index": 3, "pred_merged23": 3, "pred_correct": 1},  # not in baseline
    ]}
    c = compare_baseline(data, baseline, 0.9934)
    ok = (c["n_pair"] == 3 and abs(c["prediction_agreement"] - 2 / 3) < 1e-9
          and abs(c["rf_accuracy"] - 2 / 3) < 1e-9
          and abs(c["accuracy_delta_pp"] - 100 * (2 / 3 - 0.9934)) < 1e-6)
    return ok, "baseline_pairing"


def self_test():
    sc = _run_scenarios()
    passed = 0
    for name, text, expected in sc:
        data = parse_log(text)
        rep = analyze(data)
        ok = (rep["verdict"] == expected)
        if name == "healthy":
            ok = ok and rep["nominal"]
        print("  [self-test] %-24s expected=%-34s got=%-34s %s"
              % (name, expected, rep["verdict"], "OK" if ok else "FAIL"))
        passed += 1 if ok else 0
    b_ok, b_name = _self_test_baseline()
    print("  [self-test] %-24s %s" % (b_name, "OK" if b_ok else "FAIL"))
    passed += 1 if b_ok else 0
    return passed, len(sc) + 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv):
    ap = argparse.ArgumentParser(
        description="fix9r Task A root-cause analyzer for the fix9 RF loopback log")
    ap.add_argument("--log", help="path to the fix9 run log (stdout capture)")
    ap.add_argument("--baseline", help="path to route_f_fix9r_exact_baseline.tsv")
    ap.add_argument("--baseline-accuracy", type=float, default=0.9934,
                    help="known original-data accuracy (906/912) for the §9 delta")
    ap.add_argument("--json", help="write the full report to this JSON path")
    ap.add_argument("--self-test", action="store_true",
                    help="run the built-in synthetic self-tests and exit")
    args = ap.parse_args(argv)

    if args.self_test:
        passed, total = self_test()
        print("analyze_iq_rf_loopback_recovery: self-test %d/%d"
              % (passed, total))
        return 0 if passed == total else 1

    if not args.log:
        ap.error("--log is required (or use --self-test)")

    with open(args.log, "r", encoding="utf-8") as fh:
        text = fh.read()

    data = parse_log(text)
    rep = analyze(data)

    print("=== fix9r root-cause analysis ===")
    s = rep["stats"]
    print("files=%d rf_fidelity=%d tensor=%d scored=%d correct=%d accuracy=%s"
          % (s["n_files"], s["n_rf_fidelity"], s["n_tensor"],
             s["n_scored"], s["n_correct"],
             ("%.4f" % s["accuracy"]) if s["accuracy"] is not None else "n/a"))
    print("phase: mean=%.2f deg  circular_std=%.2f deg  rebuild_delta(mean|max)=%.2f|%.2f deg"
          % (_d(s["phase_mean_deg"]), _d(s["phase_circular_std_deg"]),
             _d(s["phase_rebuild_delta_mean_abs_deg"]),
             _d(s["phase_rebuild_delta_max_abs_deg"])))
    print("gain_mag: median=%.6f min=%.6f max=%.6f rel_std=%.4f"
          % (_d(s["gain_mag_median"]), _d(s["gain_mag_min"]),
             _d(s["gain_mag_max"]), _d(s["gain_mag_rel_std"])))
    print("cfo_hz: max_abs=%.2f   phase_drift: max_abs=%.2f deg"
          % (_d(s["cfo_hz_max_abs"]), _d(s["phase_drift_max_abs_deg"])))
    print("rf_corr: median=%.4f min=%.4f   tensor_nmse: median=%.4f max=%.4f   "
          "tensor_corr: median=%.4f min=%.4f"
          % (_d(s["rf_corr_median"]), _d(s["rf_corr_min"]),
             _d(s["tensor_nmse_median"]), _d(s["tensor_nmse_max"]),
             _d(s["tensor_corr_median"]), _d(s["tensor_corr_min"])))
    if "global_gain_mag" in s:
        print("global_gain: mag=%.6f phase=%.3f deg  k_mag=%.6f k_phase=%.3f deg"
              % (_d(s["global_gain_mag"]), _d(s["global_gain_phase_deg"]),
                 _d(s["global_gain_k_mag"]), _d(s["global_gain_k_phase_deg"])))
    print("pred_merged23_histogram: %s"
          % json.dumps(s["pred_merged23_histogram"], sort_keys=True))
    print("evidence: %s" % ", ".join(rep["evidence"]))
    print("VERDICT: %s%s" % (rep["verdict"], " (nominal)" if rep["nominal"] else ""))

    report = rep
    if args.baseline:
        base = load_baseline(args.baseline)
        cmp_ = compare_baseline(data, base, args.baseline_accuracy)
        print("\n=== exact-baseline comparison (Task F gate) ===")
        if cmp_.get("n_pair") == 0:
            print("n_pair=0 (no source_index matched the baseline TSV; ensure the "
                  "log carries IQ_RF_LOOPBACK_D2_RESTORE source_index= lines)")
        else:
            print("n_pair=%d prediction_agreement=%.4f baseline_accuracy=%.4f "
                  "rf_accuracy=%.4f accuracy_delta_pp=%.2f"
                  % (cmp_["n_pair"], cmp_["prediction_agreement"],
                     cmp_["baseline_accuracy"], cmp_["rf_accuracy"],
                     cmp_["accuracy_delta_pp"]))
        report = dict(report)
        report["baseline_comparison"] = cmp_

    if args.json:
        # per-file dicts carry None for missing fields; keep JSON serializable.
        serializable = _strip_none(report)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(serializable, fh, indent=2, sort_keys=True)
        print("wrote %s" % args.json)

    return 0


def _d(x):
    return 0.0 if x is None else x


def _strip_none(o):
    if isinstance(o, dict):
        return {k: _strip_none(v) for k, v in o.items() if v is not None}
    if isinstance(o, list):
        return [_strip_none(v) for v in o]
    return o


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
