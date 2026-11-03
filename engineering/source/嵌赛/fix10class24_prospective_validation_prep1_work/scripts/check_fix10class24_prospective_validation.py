#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_fix10class24_prospective_validation.py — 前瞻验证自动判读工具 (fix10class24
prospective-validation prep1, task 39e5).

Reads a real-RF positive-results table, a negative-results table, and the FROZEN
candidate-gate policy, then reports -- WITHOUT ever recommending a new production
threshold -- how each candidate gate would behave on the (future) independent set:

  * 24-class coverage + per-class repeat sufficiency
  * primary-key uniqueness
  * positive/negative non-mixing
  * finiteness of all recovery metrics
  * baseline identity match (frozen BF16 baseline, model sha 28272abc...)
  * WC (17) / SC (18) kept independent (never 24->23 merged)
  * per-candidate positive admit rate, per-class admit rate, false-reject rate
  * negative false-admit rate (误接纳率)
  * admitted-sample raw24 prediction-agreement rate
  * Wilson 95% CI (or, at minimum, the sample-count denominator)

Exit code 0 when every HARD check passes; 1 otherwise.  The per-candidate rates are
informational (never a PASS/FAIL, and never a threshold recommendation).  Insufficient
evidence is reported as INSUFFICIENT_EVIDENCE, not as a silent pass.

The FROZEN baseline and negative-type vocabulary are embedded here on purpose: the
baseline (model sha 28272abc...) and the 24 clean-IQ source identities are frozen
assets, so the checker verifies "baseline identity match" against them directly rather
than trusting the results file's own labels.
"""

import argparse
import csv
import hashlib
import json
import math
import os
import sys

# ---------------------------------------------------------------------------
# FROZEN assets (do not edit).  These mirror
#   baselines/clean24_smoke_raw24_bf16_baseline.tsv
#   clean24_smoke/route_d2_rf_manifest.tsv
# ---------------------------------------------------------------------------
FROZEN_MODEL_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"

# source_index -> frozen BF16 raw24 top-1 prediction (24/24 clean-IQ correct).
FROZEN_BASELINE = {
    0: 0, 500: 1, 1000: 2, 1500: 3, 2000: 4, 2500: 5, 3000: 6, 3500: 7,
    4000: 8, 4500: 9, 5000: 10, 5500: 11, 6000: 12, 6500: 13, 7000: 14, 7500: 15,
    8000: 16, 8500: 17, 9000: 18, 9500: 19, 10000: 20, 10500: 21, 11000: 22, 11500: 23,
}

# source_index -> (raw24_class, modulation), the frozen 24-class identity.
FROZEN_IDENTITY = {
    0: (0, "OOK"), 500: (1, "4ASK"), 1000: (2, "8ASK"), 1500: (3, "BPSK"),
    2000: (4, "QPSK"), 2500: (5, "8PSK"), 3000: (6, "16PSK"), 3500: (7, "32PSK"),
    4000: (8, "16APSK"), 4500: (9, "32APSK"), 5000: (10, "64APSK"), 5500: (11, "128APSK"),
    6000: (12, "16QAM"), 6500: (13, "32QAM"), 7000: (14, "64QAM"), 7500: (15, "128QAM"),
    8000: (16, "256QAM"), 8500: (17, "AM-SSB-WC"), 9000: (18, "AM-SSB-SC"),
    9500: (19, "AM-DSB-WC"), 10000: (20, "AM-DSB-SC"), 10500: (21, "FM"),
    11000: (22, "GMSK"), 11500: (23, "OQPSK"),
}

EXPECTED_CLASSES = sorted(FROZEN_IDENTITY.values())          # 24 (raw24_class, modulation) pairs
WC_CLASS = 17
SC_CLASS = 18

NEGATIVE_VOCAB = [
    "no_signal", "noise_only", "tx_off", "wrong_center_freq", "cfo_out_of_range",
    "low_training_corr", "wrong_window_or_sync", "incomplete_burst", "severe_clipping",
    "too_low_amplitude", "wrong_training_frame", "random_non_training_iq",
    "network_interrupt_or_tx_early_stop",
]

# production fine-CFO bound (kFs / (2 * kTailStart) == 2560000 / 117760), from
# iqrfrec::config in the production runner.
PRODUCTION_CFO_MAX_HZ = 21.739

Z95 = 1.959963984540054  # 95% two-sided


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _to_float(s):
    """Parse a float; tolerate NaN/Inf/Infinity and the board's lowercase nan."""
    if s is None:
        return None
    s = s.strip()
    if s == "":
        return None
    low = s.lower()
    if low in ("nan", "+nan", "-nan"):
        return math.nan
    if low in ("inf", "+inf", "infinity", "+infinity"):
        return math.inf
    if low in ("-inf", "-infinity"):
        return -math.inf
    try:
        return float(s)
    except ValueError:
        return None


def _to_int(s):
    if s is None:
        return None
    s = s.strip()
    if s == "":
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def wilson(k, n, z=Z95):
    if n <= 0:
        return None
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def is_finite(x):
    return x is not None and math.isfinite(x)


# ---------------------------------------------------------------------------
# TSV loaders (index by header name, so column order is non-fragile)
# ---------------------------------------------------------------------------
def load_tsv(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        raw = [row for row in reader]
    if not raw:
        raise SystemExit("check: empty TSV: " + path)
    header = [c.strip() for c in raw[0]]
    rows = []
    for i, row in enumerate(raw[1:], start=2):
        if not row or all(not c.strip() for c in row):
            continue
        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))
        d = {header[j]: (row[j].strip() if j < len(row) else "") for j in range(len(header))}
        rows.append(d)
    return header, rows


def load_policy(path):
    header, rows = load_tsv(path)
    policies = []
    for d in rows:
        policies.append({
            "policy_id": d.get("policy_id", ""),
            "policy_name": d.get("policy_name", ""),
            "kind": d.get("kind", ""),
            "residual_max": _to_float(d.get("residual_max")),
            "payload_training_corr_min": _to_float(d.get("payload_training_corr_min")),
            "training_corr_min": _to_float(d.get("training_corr_min")),
            "cfo_max_hz": _to_float(d.get("cfo_max_hz")),
            "require_not_clipped": _to_int(d.get("require_not_clipped")),
            "frozen_by": d.get("frozen_by", ""),
            "description": d.get("description", ""),
        })
    return policies


# ---------------------------------------------------------------------------
# gate predicate
# ---------------------------------------------------------------------------
def admits(policy, m):
    """m is a dict of parsed numeric metrics. Returns True when the candidate gate
    admits the sample.  Every candidate retains the production corr/CFO/clip validity
    gates and only varies the residual bound (and, for joint candidates, tightens the
    payload-training correlation)."""
    resid = m["payload_training_residual"]
    pcorr = m["payload_training_corr"]
    tcorr = m["training_corr"]
    cfo = m["cfo_hz"]
    clip = m["rx_clipped"]
    if not (is_finite(resid) and is_finite(pcorr) and is_finite(tcorr) and is_finite(cfo)):
        return False
    if not (resid <= policy["residual_max"]):
        return False
    if not (pcorr >= policy["payload_training_corr_min"]):
        return False
    if not (tcorr >= policy["training_corr_min"]):
        return False
    if abs(cfo) > policy["cfo_max_hz"]:
        return False
    if policy["require_not_clipped"] and clip == 1:
        return False
    return True


# ---------------------------------------------------------------------------
# parse a results row into numeric metrics
# ---------------------------------------------------------------------------
POS_METRIC_COLS = ["payload_training_residual", "payload_training_corr",
                   "training_corr", "cfo_hz", "rx_clipped", "gate_admitted",
                   "raw24_pred", "baseline_pred", "label_correct",
                   "prediction_agreement", "finite"]


def parse_metrics(d):
    m = {}
    m["payload_training_residual"] = _to_float(d.get("payload_training_residual"))
    m["payload_training_corr"] = _to_float(d.get("payload_training_corr"))
    m["training_corr"] = _to_float(d.get("training_corr"))
    m["cfo_hz"] = _to_float(d.get("cfo_hz"))
    m["rx_clipped"] = _to_int(d.get("rx_clipped"))
    m["gate_admitted"] = _to_int(d.get("gate_admitted"))
    m["raw24_pred"] = _to_int(d.get("raw24_pred"))
    m["baseline_pred"] = _to_int(d.get("baseline_pred"))
    m["label_correct"] = _to_int(d.get("label_correct"))
    m["prediction_agreement"] = _to_int(d.get("prediction_agreement"))
    m["finite"] = _to_int(d.get("finite"))
    m["source_index"] = _to_int(d.get("source_index"))
    m["raw24_class"] = _to_int(d.get("raw24_class"))
    return m


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------
def run_checks(positive, negative, policies, min_repeat):
    hard = []          # list of (name, ok, detail)
    report = {}

    # -- 1. coverage: exactly the 24 classes, each with >= min_repeat --
    pos_by_class = {}
    for d in positive:
        rc = _to_int(d.get("raw24_class"))
        pos_by_class.setdefault(rc, []).append(d)
    present = sorted(c for c in pos_by_class if c is not None)
    expected_classes = sorted({c for c, _ in EXPECTED_CLASSES})
    missing = [c for c in expected_classes if c not in present]
    extra = [c for c in present if c not in expected_classes]
    repeat_short = []
    for c in expected_classes:
        n = len(pos_by_class.get(c, []))
        if n < min_repeat:
            repeat_short.append((c, n))
    coverage_ok = (missing == [] and extra == [] and repeat_short == [])
    hard.append(("class_coverage", coverage_ok,
                 "missing=%s extra=%s repeat_short=%s min_repeat=%d" % (
                     missing, extra, repeat_short, min_repeat)))
    report["class_coverage"] = {
        "ok": coverage_ok, "expected_classes": expected_classes,
        "present_classes": present, "missing": missing, "extra": extra,
        "repeat_short": repeat_short, "min_repeat": min_repeat,
    }

    # -- 2. primary-key uniqueness (capture_id) + (source_index, repeat_id) --
    cids = [d.get("capture_id", "") for d in positive]
    dup_cid = sorted({c for c in cids if cids.count(c) > 1})
    sr_keys = [(d.get("source_index", ""), d.get("repeat_id", "")) for d in positive]
    dup_sr = sorted({k for k in sr_keys if sr_keys.count(k) > 1})
    pk_ok = (dup_cid == [] and dup_sr == [])
    hard.append(("primary_key_unique", pk_ok,
                 "duplicate_capture_id=%s duplicate_(source_index,repeat_id)=%s" % (
                     dup_cid, dup_sr)))

    # -- 3. positive/negative non-mixing --
    neg_cids = set(d.get("capture_id", "") for d in negative)
    pos_cids = set(cids)
    overlap = sorted(neg_cids & pos_cids)
    neg_has_negtype = all(d.get("negative_type", "").strip() for d in negative)
    neg_type_valid = all(d.get("negative_type", "").strip() in NEGATIVE_VOCAB for d in negative)
    pos_has_negtype = any(d.get("negative_type", "").strip() for d in positive)
    mix_ok = (overlap == [] and neg_has_negtype and neg_type_valid and not pos_has_negtype)
    hard.append(("positive_negative_not_mixed", mix_ok,
                 "capture_id_overlap=%s neg_all_have_type=%s neg_type_valid=%s "
                 "pos_has_negative_type=%s" % (
                     overlap, neg_has_negtype, neg_type_valid, pos_has_negtype)))

    # -- 4. finiteness of all recovery metrics --
    nonfinite = []
    for d in positive + negative:
        m = parse_metrics(d)
        for col in ["payload_training_residual", "payload_training_corr",
                    "training_corr", "cfo_hz"]:
            if not is_finite(m[col]):
                nonfinite.append((d.get("capture_id", "?"), col))
        if m["rx_clipped"] not in (0, 1):
            nonfinite.append((d.get("capture_id", "?"), "rx_clipped"))
    finite_ok = (nonfinite == [])
    hard.append(("all_values_finite", finite_ok, "nonfinite=%s" % nonfinite[:20]))

    # -- 5. baseline identity match --
    baseline_bad = []
    for d in positive:
        m = parse_metrics(d)
        si = m["source_index"]
        if si not in FROZEN_BASELINE:
            baseline_bad.append((d.get("capture_id", "?"), si, "unknown_source_index"))
            continue
        if m["baseline_pred"] is not None and m["baseline_pred"] != FROZEN_BASELINE[si]:
            baseline_bad.append((d.get("capture_id", "?"), si,
                                 "pred=%s expected=%s" % (m["baseline_pred"],
                                                          FROZEN_BASELINE[si])))
        # source_index -> raw24_class identity must match frozen identity
        if m["raw24_class"] is not None and FROZEN_IDENTITY[si][0] != m["raw24_class"]:
            baseline_bad.append((d.get("capture_id", "?"), si,
                                 "raw24_class=%s expected=%s" % (
                                     m["raw24_class"], FROZEN_IDENTITY[si][0])))
    baseline_ok = (baseline_bad == [])
    hard.append(("baseline_identity_match", baseline_ok, "mismatch=%s" % baseline_bad[:20]))

    # -- 6. WC/SC independent (never merged) --
    wc = pos_by_class.get(WC_CLASS, [])
    sc = pos_by_class.get(SC_CLASS, [])
    wc_mods = {d.get("modulation", "").strip() for d in wc}
    sc_mods = {d.get("modulation", "").strip() for d in sc}
    wc_sc_ok = (len(wc) > 0 and len(sc) > 0 and "AM-SSB-WC" in wc_mods and
                "AM-SSB-SC" in sc_mods and wc_mods != sc_mods)
    hard.append(("wc_sc_independent", wc_sc_ok,
                 "wc_modulations=%s sc_modulations=%s" % (wc_mods, sc_mods)))

    report["hard_checks"] = [{"name": n, "ok": o, "detail": det}
                             for n, o, det in hard]
    return hard, report, pos_by_class, parse_metrics, wc, sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--positive-results", required=True)
    ap.add_argument("--negative-results", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--identity", default=None)
    ap.add_argument("--min-repeat", type=int, default=3)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    _, positive = load_tsv(args.positive_results)
    _, negative = load_tsv(args.negative_results)
    policies = load_policy(args.policy)

    # If --identity given, cross-check it against the embedded frozen identity.
    identity_note = ""
    if args.identity:
        _, ident = load_tsv(args.identity)
        ident_classes = sorted({int(d["raw24_class"]) for d in ident})
        expected = sorted({c for c, _ in EXPECTED_CLASSES})
        identity_note = ("identity_file_classes=%s match=%s" % (
            ident_classes, ident_classes == expected))

    hard, report, pos_by_class, parse_metrics, wc, sc = run_checks(
        positive, negative, policies, args.min_repeat)

    # ---- per-candidate statistics (informational) ----
    def _n(sample): return len(sample)

    per_policy = []
    for pol in policies:
        pid = pol["policy_id"]
        # positive
        admitted_pos = [d for d in positive if admits(pol, parse_metrics(d))]
        n_pos = _n(positive)
        admit_rate = len(admitted_pos) / n_pos if n_pos else None
        # per-class admit rate
        class_admit = {}
        for c in sorted(pos_by_class):
            cc = pos_by_class[c]
            ca = [d for d in cc if admits(pol, parse_metrics(d))]
            class_admit[c] = (len(ca), len(cc))
        # false reject (positive not admitted) = 1 - admit_rate
        false_reject = (1.0 - admit_rate) if admit_rate is not None else None
        # negative false-admit
        admitted_neg = [d for d in negative if admits(pol, parse_metrics(d))]
        n_neg = _n(negative)
        neg_false_admit = len(admitted_neg) / n_neg if n_neg else None
        # admitted prediction agreement (positive, finite)
        admit_finite = [d for d in admitted_pos
                        if parse_metrics(d)["finite"] == 1 and
                        parse_metrics(d)["prediction_agreement"] is not None]
        agree = [d for d in admit_finite if parse_metrics(d)["prediction_agreement"] == 1]
        n_af = _n(admit_finite)
        agree_rate = len(agree) / n_af if n_af else None
        # WC / SC separately
        wc_adm = [d for d in wc if admits(pol, parse_metrics(d))]
        sc_adm = [d for d in sc if admits(pol, parse_metrics(d))]

        per_policy.append({
            "policy_id": pid,
            "kind": pol["kind"],
            "residual_max": pol["residual_max"],
            "n_positive": n_pos,
            "positive_admitted": len(admitted_pos),
            "positive_admit_rate": admit_rate,
            "positive_admit_ci95": wilson(len(admitted_pos), n_pos),
            "false_reject_rate": false_reject,
            "n_negative": n_neg,
            "negative_false_admitted": len(admitted_neg),
            "negative_false_admit_rate": neg_false_admit,
            "negative_false_admit_ci95": wilson(len(admitted_neg), n_neg),
            "admitted_agreement_denominator": n_af,
            "admitted_agreement_numerator": len(agree),
            "admitted_agreement_rate": agree_rate,
            "admitted_agreement_ci95": wilson(len(agree), n_af),
            "wc_n": _n(wc), "wc_admitted": len(wc_adm),
            "sc_n": _n(sc), "sc_admitted": len(sc_adm),
            "per_class": class_admit,
        })

    report["policy_sha256"] = sha256_file(args.policy)
    report["positive_sha256"] = sha256_file(args.positive_results)
    report["negative_sha256"] = sha256_file(args.negative_results)
    report["frozen_model_sha256"] = FROZEN_MODEL_SHA
    report["identity_note"] = identity_note
    report["n_positive"] = _n(positive)
    report["n_negative"] = _n(negative)
    report["no_new_production_threshold"] = True
    report["per_policy"] = per_policy

    # ---- write outputs ----
    with open(os.path.join(args.out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, allow_nan=True)

    with open(os.path.join(args.out_dir, "per_policy.tsv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(["policy_id", "kind", "residual_max", "n_positive",
                    "positive_admitted", "positive_admit_rate", "false_reject_rate",
                    "n_negative", "negative_false_admitted", "negative_false_admit_rate",
                    "admitted_agreement_denominator", "admitted_agreement_rate",
                    "wc_n", "wc_admitted", "sc_n", "sc_admitted"])
        for pp in per_policy:
            w.writerow([pp["policy_id"], pp["kind"], pp["residual_max"], pp["n_positive"],
                        pp["positive_admitted"], _fmt(pp["positive_admit_rate"]),
                        _fmt(pp["false_reject_rate"]), pp["n_negative"],
                        pp["negative_false_admitted"], _fmt(pp["negative_false_admit_rate"]),
                        pp["admitted_agreement_denominator"],
                        _fmt(pp["admitted_agreement_rate"]),
                        pp["wc_n"], pp["wc_admitted"], pp["sc_n"], pp["sc_admitted"]])

    # ---- human summary ----
    lines = []
    lines.append("PROSPECTIVE_VALIDATION_CHECKER (task 39e5 prep1)")
    lines.append("policy_sha256=%s" % report["policy_sha256"])
    lines.append("positive_sha256=%s" % report["positive_sha256"])
    lines.append("negative_sha256=%s" % report["negative_sha256"])
    lines.append("frozen_model_sha256=%s" % FROZEN_MODEL_SHA)
    lines.append("n_positive=%d n_negative=%d" % (report["n_positive"], report["n_negative"]))
    if identity_note:
        lines.append("identity=%s" % identity_note)
    lines.append("")
    lines.append("HARD CHECKS:")
    for h in hard:
        lines.append("  [%s] %s: %s" % ("PASS" if h[1] else "FAIL", h[0], h[2]))
    lines.append("")
    lines.append("PER-CANDIDATE (informational; NO threshold recommendation):")
    for pp in per_policy:
        lines.append("  %-34s admit=%s/%s (%s) false_reject=%s neg_false_admit=%s/%s (%s) "
                     "agree=%s/%s (%s) wc=%s/%s sc=%s/%s" % (
                         pp["policy_id"],
                         pp["positive_admitted"], pp["n_positive"],
                         _pct(pp["positive_admit_rate"]),
                         _pct(pp["false_reject_rate"]),
                         pp["negative_false_admitted"], pp["n_negative"],
                         _pct(pp["negative_false_admit_rate"]),
                         pp["admitted_agreement_numerator"],
                         pp["admitted_agreement_denominator"],
                         _pct(pp["admitted_agreement_rate"]),
                         pp["wc_admitted"], pp["wc_n"],
                         pp["sc_admitted"], pp["sc_n"]))
    lines.append("")
    lines.append("no_new_production_threshold=1 (informational only; production 0.100 unchanged)")

    text = "\n".join(lines) + "\n"
    with open(os.path.join(args.out_dir, "report.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    sys.stdout.write(text)

    all_ok = all(h[1] for h in hard)
    return 0 if all_ok else 1


def _fmt(x):
    if x is None:
        return ""
    if not is_finite(x):
        return str(x)
    return "%.6f" % x


def _pct(x):
    if x is None:
        return "INSUFFICIENT_EVIDENCE"
    return "%.1f%%" % (100.0 * x)


if __name__ == "__main__":
    sys.exit(main())
