#!/usr/bin/env python3
"""self_check.py -- automated self-consistency assertions over the Stage A/B/C
outputs.  Verifies structure and the decisive numbers are present and unchanged.
Read-only; exits non-zero on any failure.
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

FAILURES = []


def check(cond, msg):
    if cond:
        print("  OK   %s" % msg)
    else:
        FAILURES.append(msg)
        print("  FAIL %s" % msg)


def main():
    dc = json.load(open(os.path.join(OUT, "domain_comparison.json"), encoding="utf-8"))
    ab = json.load(open(os.path.join(OUT, "preprocess_ablation.json"), encoding="utf-8"))

    print("domain_comparison.json:")
    check(len(dc["real"]["top1_histogram"]) >= 3, "real top-1 histogram has QAM classes")
    check(dc["real"]["top1_histogram"].get("QPSK", 0) == 0, "real top-1 has 0 QPSK")
    check(dc["radioml"]["top1_histogram"].get("QPSK", 0) == 200, "RadioML top-1 has 200 QPSK")
    check(len(dc["input_sha256"]) == 78, "78 real input SHA256 recorded")
    check(len(dc["radioml"]["activation_rms"]) == 66, "66 intermediate activation layers")
    r = dc["real"]["spectral_summary"]; m = dc["radioml"]["spectral_summary"]
    check(r["env_sq_clean_symbol_line"] is True and abs(r["env_sq_top_peak_hz"] - 16000) < 1,
          "real has clean 16 kHz symbol line")
    check(m["env_sq_clean_symbol_line"] is False, "RadioML envelope line is smeared")
    check(dc["real"]["stats"]["papr_db"]["mean"] < dc["radioml"]["stats"]["papr_db"]["mean"],
          "real PAPR < RadioML PAPR")

    # activation RMS ratio real/rm (mean ~1.26)
    rm_a = dc["radioml"]["activation_rms"]; re_a = dc["real"]["activation_rms"]
    ratios = [re_a[k]["rms_mean"] / rm_a[k]["rms_mean"] for k in rm_a]
    mean_ratio = sum(ratios) / len(ratios)
    check(1.15 < mean_ratio < 1.40, "mean activation RMS ratio real/rm in (1.15,1.40): %.3f" % mean_ratio)

    print("preprocess_ablation.json:")
    rows = {x["transform"]: x for x in ab["rows"]}
    check(rows["1_no_processing_baseline"]["qpsk_top1_count"] == 0, "baseline 0 QPSK")
    check(rows["11_bw_align_lowpass"]["qpsk_top1_count"] == 35, "bw_align 35/78 QPSK")
    check(rows["11_bw_align_lowpass"]["radioml_golden_qpsk_count"] == 179, "bw_align golden 179/200")
    check(rows["2_per_frame_complex_dc_removal"]["radioml_golden_qpsk_count"] == 111,
          "dc_removal golden 111/200 (brittleness)")
    check(rows["12_exact_training_loader"]["qpsk_top1_count"] == 0, "exact loader == baseline (identity)")
    # every other transform (non bw_align) <= 1 QPSK
    low = [k for k, x in rows.items()
           if k not in ("11_bw_align_lowpass",) and x["qpsk_top1_count"] > 1]
    check(not low, "no non-bw_align transform recovers >1 QPSK: %s" % low)

    print()
    if FAILURES:
        print("SELF-CHECK FAILED (%d):" % len(FAILURES))
        for f in FAILURES:
            print("  -", f)
        raise SystemExit(1)
    print("SELF-CHECK PASSED")


if __name__ == "__main__":
    main()
