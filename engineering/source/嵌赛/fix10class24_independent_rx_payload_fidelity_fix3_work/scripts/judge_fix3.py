#!/usr/bin/env python3
"""judge_fix3.py -- Fix3 final verdict (fail-closed).

Consolidates every Phase A/B/C artifact in results/ into a single evidence-based
verdict.  The verdict is NEGATIVE by design: this task's job is to determine,
without training and without touching the frozen model / gate / label order,
whether a category-independent no-training recovery fix within the red lines can
recover the frozen-BF16 24-class accuracy on the RF capture.  The evidence says
no; this script records that conclusion with the numbers, and fails closed (exit
!= 0) if any required artifact is missing or contradicts the conclusion.

Verdict conditions (all must hold):
  V1  frozen model json/raw SHA match the contract.
  V2  Phase A: host reproduces the board collapse byte-for-byte (1/24 correct,
      23 gated, 1 reject, argmax/logit agreement 23/23).
  V3  Phase B: the wide-linear inverse denom |a|^2-|b|^2 ~ 1e-3 on the RF capture
      (median < 1e-2), i.e. the amplification mechanism is present.
  V4  Phase C cross-session: digital file loopback is clean (denom ~ 1, accuracy
      high) while RF dual is collapsed (denom ~ 1e-3, accuracy low).
  V5  Phase C offset models: no no-oracle model (M0..M4) recovers accuracy
      (max correct/24 <= 4); the oracle bound M5 is reported but is forbidden.
  V6  Phase C synthetic counterexample: the same injected DC is amplified at
      least 5x more by the RF-like channel than the digital channel.

Exit 0 = verdict reached (analysis completed; conclusion recorded).  Exit 1 =
fail-closed (missing/inconsistent artifact).  No board, no SDR, no training.

Usage:
    python -I scripts/judge_fix3.py --results-dir results \
        --model-dir F:/嵌赛/.../model_rml24_bf16 [--out results/final_verdict.json]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fix3_common as c


def _num(s: str) -> float:
    return float(s)


def _read_tsv_cols(path: Path, header: list[str]) -> list[dict]:
    h, rows = c.read_tsv(path)
    if h != header:
        c.fail("TSV %s header mismatch" % path)
    return rows


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out", default="results/final_verdict.json")
    args = ap.parse_args(argv)

    rd = Path(args.results_dir)
    model_dir = Path(args.model_dir)

    checks: list[dict] = []
    def check(name: str, ok: bool, detail: str):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            c.fail("check %s failed: %s" % (name, detail))

    # V1 frozen model identity
    mj = c.sha256_file(model_dir / "rml24_adamrv11_bf16.json")
    mr = c.sha256_file(model_dir / "rml24_adamrv11_bf16.raw")
    check("V1_model_json_sha", mj == c.FROZEN_MODEL_JSON_SHA256,
          "json sha %s" % mj)
    check("V1_model_raw_sha", mr == c.FROZEN_MODEL_RAW_SHA256,
          "raw sha %s" % mr)

    # V2 Phase A summary
    import json
    a_summary = json.loads((rd / "summary.json").read_text(encoding="utf-8"))
    check("V2_host_reproduces_collapse",
          a_summary.get("correct") == 1 and a_summary.get("gated") == 23
          and a_summary.get("gate_reject") == 1,
          "Phase A: correct=%s gated=%s reject=%s"
          % (a_summary.get("correct"), a_summary.get("gated"),
             a_summary.get("gate_reject")))
    check("V2_byte_exact_reproduction",
          a_summary.get("argmax_agree") == 23
          and a_summary.get("logit_byte_agree") == 23,
          "argmax_agree=%s logit_byte_agree=%s"
          % (a_summary.get("argmax_agree"), a_summary.get("logit_byte_agree")))

    # V3 Phase B denom
    b_rows = _read_tsv_cols(
        rd / "per_sample_layer_metrics.tsv",
        ["source_index", "class_index", "class_name",
         "settle_dc_re", "settle_dc_im", "settle_rms",
         "guard_dc_re", "guard_dc_im", "guard_rms",
         "payload_dc_re", "payload_dc_im", "payload_rms",
         "payload_dc_slope_re", "payload_dc_slope_im",
         "derot_payload_dc_re", "derot_payload_dc_im",
         "wl_first1024_dc_re", "wl_first1024_dc_im",
         "wl_first1024_rms",
         "recovered_dc_re", "recovered_dc_im", "recovered_rms",
         "clean_dc_re", "clean_dc_im", "clean_rms",
         "corr", "best_gain_re", "best_gain_im",
         "resid_after_gain", "resid_after_gain_dc",
         "wl_denom", "a_mag", "b_mag",
         "training_residual_rel", "gated", "board_pred"])
    denoms = sorted(_num(r["wl_denom"]) for r in b_rows)
    med_denom = denoms[len(denoms) // 2]
    check("V3_wl_denom_small", med_denom < 1e-2,
          "median wl_denom=%.6f (RF capture)" % med_denom)

    # V4 cross-session
    x_rows = _read_tsv_cols(
        rd / "cross_session_validation.tsv",
        ["session", "a_mag", "b_mag", "wl_denom", "cfo_min", "cfo_max",
         "correct", "gated", "classified", "end_to_end_accuracy"])
    by_session = {r["session"]: r for r in x_rows}
    if "digital_file_loopback" not in by_session or "rf_dual_sdr" not in by_session:
        c.fail("cross-session missing session rows")
    dig = by_session["digital_file_loopback"]
    rf = by_session["rf_dual_sdr"]
    check("V4_digital_clean", _num(dig["wl_denom"]) > 0.9
          and _num(dig["end_to_end_accuracy"]) > 0.8,
          "digital denom=%s e2e=%s" % (dig["wl_denom"], dig["end_to_end_accuracy"]))
    check("V4_rf_collapsed", _num(rf["wl_denom"]) < 1e-2
          and _num(rf["end_to_end_accuracy"]) < 0.2,
          "rf denom=%s e2e=%s" % (rf["wl_denom"], rf["end_to_end_accuracy"]))

    # V5 offset models
    v_summary = json.loads((rd / "validation_summary.json").read_text(encoding="utf-8"))
    om = v_summary["offset_models"]
    no_oracle = [m for m in om if m != "M5_oracle_dc"]
    best = max(om[m]["correct"] for m in no_oracle)
    check("V5_no_oracle_fails", best <= 4,
          "max no-oracle correct=%d/24 (M0..M4)" % best)

    # V6 synthetic counterexample
    syn = _read_tsv_cols(
        rd / "synthetic_counterexamples.tsv",
        ["inj_dc_re", "inj_dc_im", "channel", "a_mag", "b_mag", "wl_denom",
         "recovered_dc_re", "recovered_dc_im", "recovered_dc_mag",
         "dc_amplification_vs_digital"])
    amps = [float(r["dc_amplification_vs_digital"]) for r in syn
            if r["dc_amplification_vs_digital"] != ""]
    check("V6_amplification_demonstrated", bool(amps) and max(amps) >= 5.0,
          "max DC amplification (RF vs digital) = %.2fx" % (max(amps) if amps else 0.0))

    verdict = {
        "status": "FIX3_COMPLETE_NO_TRAINING_FIX_WITHIN_RED_LINES",
        "conclusion": (
            "No category-independent no-training recovery fix within the red "
            "lines recovers the frozen-BF16 24-class accuracy on the RF capture. "
            "The collapse (1/24 correct, 19x AM-SSB-SC + 4x AM-SSB-WC) is "
            "RF-specific and driven by a slowly time-varying DC offset that the "
            "wide-linear inverse amplifies ~10-15x (normalized) / ~1000x (denom "
            "= |a|^2-|b|^2 ~ 1e-3). Digital file loopback (denom ~ 1) reaches "
            "23/24. Real RF fine-tuning, or a fundamentally more robust recovery, "
            "is required -- NOT performed in this task."
        ),
        "key_numbers": {
            "phase_a_correct": a_summary.get("correct"),
            "phase_a_gated": a_summary.get("gated"),
            "phase_b_median_wl_denom": med_denom,
            "digital_e2e_accuracy": dig["end_to_end_accuracy"],
            "rf_e2e_accuracy": rf["end_to_end_accuracy"],
            "digital_wl_denom": dig["wl_denom"],
            "rf_wl_denom": rf["wl_denom"],
            "best_no_oracle_correct": best,
            "oracle_bound_correct": om["M5_oracle_dc"]["correct"],
            "max_dc_amplification_rf_vs_digital": max(amps) if amps else None,
        },
        "checks": checks,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c.dumps_json(verdict, out)

    print("[judge] VERDICT: %s" % verdict["status"])
    for k, v in verdict["key_numbers"].items():
        print("  %-34s = %s" % (k, v))
    print("[judge] %d/%d checks passed" %
          (sum(1 for ch in checks if ch["ok"]), len(checks)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
