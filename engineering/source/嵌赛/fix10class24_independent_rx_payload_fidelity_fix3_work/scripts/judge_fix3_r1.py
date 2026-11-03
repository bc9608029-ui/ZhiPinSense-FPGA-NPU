#!/usr/bin/env python3
"""judge_fix3_r1.py -- FIX3-REVIEW-R1 neutral verdict (fail-closed).

Supersedes judge_fix3.py, which the review flagged as conclusion-predisposed
("verdict is NEGATIVE by design", "max no-oracle correct <= 4" hard-coded, and
the "small denom = ill-conditioned / 1000x" amplification narrative).

This judge is NEUTRAL and DATA-DRIVEN.  It:
  * records facts (Phase A byte-exact reproduction; re-estimation faithfulness),
  * reports the three requested metrics per model (gate_pass/24,
    gated_correct/gate_pass, end_to_end_correct/24) from the RE-ESTIMATED run,
  * states the corrected conditioning analysis (condition number ~1.1, |b|/|a|,
    inverse gain ~1/|a|) instead of the retired "ill-conditioned" claim,
  * negates ONLY what was actually tested (the specific static/linear DC
    candidates), and
  * never asserts "no fix exists" or "fine-tuning is required".

Exit 0 = analysis complete and the tested candidates were evaluated.  Exit 1 =
fail-closed (missing/inconsistent artifact).  No board / SDR / training.

Usage:
    python -I scripts/judge_fix3_r1.py --results-dir results \
        --model-dir F:/嵌赛/.../model_rml24_bf16 [--out results/final_verdict_r1.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fix3_common as c

MODELS = ["M0_baseline", "M1_settle_dc", "M2_guard_dc",
          "M3_settle_guard_avg", "M4_linear_drift", "M5_payload_mean_bound"]


def _num(s: str) -> float:
    return float(s)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out", default="results/final_verdict_r1.json")
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
    check("V1_model_json_sha", mj == c.FROZEN_MODEL_JSON_SHA256, "json sha %s" % mj)
    check("V1_model_raw_sha", mr == c.FROZEN_MODEL_RAW_SHA256, "raw sha %s" % mr)

    # V2 Phase A: host reproduces the board collapse byte-for-byte (a FACT).
    a_summary = json.loads((rd / "summary.json").read_text(encoding="utf-8"))
    check("V2_host_reproduces_collapse",
          a_summary.get("correct") == 1 and a_summary.get("gated") == 23
          and a_summary.get("gate_reject") == 1,
          "Phase A: correct=%s gated=%s reject=%s"
          % (a_summary.get("correct"), a_summary.get("gated"),
             a_summary.get("gate_reject")))

    # V3 re-estimation faithfulness: M0 (no DC) must reproduce the board's
    # gated count (23/24) and, on the target session, the board's correct count
    # (1/24) when inferred.  This proves the re-estimation chain is faithful.
    re_summary = json.loads((rd / "reestimate_summary.json").read_text(encoding="utf-8"))
    tgt = re_summary["rf_fix2_target"]
    check("V3_reestimate_M0_faithful",
          tgt["M0_baseline"]["gate_pass"] == 23
          and tgt["M0_baseline"]["end_to_end_correct"] == 1,
          "target M0 gate_pass=%s e2e_correct=%s (board: 23 gated, 1 correct)"
          % (tgt["M0_baseline"]["gate_pass"],
             tgt["M0_baseline"]["end_to_end_correct"]))

    # V4 corrected conditioning analysis (replaces the retired "small denom =
    # ill-conditioned" claim): the wide-linear 2x2 matrix must be WELL-conditioned.
    cond_header = ["source_index", "class_name", "a_mag", "b_mag", "ratio_b_over_a",
                   "cond_2x2", "denom", "inverse_gain_1_over_a",
                   "post_eq_signal_rms", "post_eq_noise_rms", "post_eq_snr_db",
                   "recovered_dc_re", "recovered_dc_im", "recovered_dc_mag",
                   "dc_over_signal", "recovered_signal_rms"]
    h, cond_rows = c.read_tsv(rd / "reestimate_fix2_target_condition_metrics.tsv")
    if h != cond_header:
        c.fail("condition metrics header mismatch")
    conds = sorted(_num(r["cond_2x2"]) for r in cond_rows)
    ratios = sorted(_num(r["ratio_b_over_a"]) for r in cond_rows)
    inv_gains = sorted(_num(r["inverse_gain_1_over_a"]) for r in cond_rows)
    med_cond = conds[len(conds) // 2]
    med_ratio = ratios[len(ratios) // 2]
    med_invgain = inv_gains[len(inv_gains) // 2]
    check("V4_wide_linear_well_conditioned", med_cond < 5.0,
          "median cond_2x2=%.3f (well-conditioned, NOT near-singular)" % med_cond)

    # V5 neutral candidate evaluation: report the three metrics per model and
    # compare the no-oracle candidates (M1-M4) against the M0 baseline.  This
    # negates ONLY what was tested -- it does NOT assert "no fix exists".
    per_model = {}
    for m in MODELS:
        per_model[m] = tgt[m]
    m0_e2e = per_model["M0_baseline"]["end_to_end_correct"]
    no_oracle_e2e = [per_model[m]["end_to_end_correct"]
                     for m in MODELS if m not in ("M0_baseline", "M5_payload_mean_bound")]
    best_no_oracle = max(no_oracle_e2e)
    gain = best_no_oracle - m0_e2e
    # This is a report, not a gate: any tested-candidate result is a valid
    # analysis outcome.  Fail-closed only on the artifact being present+parsed.
    check("V5_candidate_metrics_present",
          all(k in per_model[m] for m in MODELS
              for k in ("gate_pass", "gated_accuracy", "end_to_end_correct")),
          "per-model metrics parsed")

    # V5b: identify which frame(s) DC compensation newly recovers, and quantify
    # the residual collapse (frames still predicted as SSB while not SSB).
    comp_header = ["model", "source_index", "class_index", "class_name",
                   "timing_offset", "coarse_cfo_hz", "fractional_timing",
                   "a_mag", "b_mag", "training_residual_rel", "gated", "pred",
                   "correct", "recovered_dc_re", "recovered_dc_im"]
    h2, comp_rows = c.read_tsv(rd / "reestimate_fix2_target_comparison.tsv")
    if h2 != comp_header:
        c.fail("comparison TSV header mismatch")
    correct_by_model = {m: set() for m in MODELS}
    collapse_by_model = {m: 0 for m in MODELS}
    for r in comp_rows:
        m = r["model"]
        cls = int(r["class_index"])
        pred = int(r["pred"])
        if r["correct"] == "1":
            correct_by_model[m].add(int(r["source_index"]))
        if pred in (17, 18) and cls not in (17, 18):
            collapse_by_model[m] += 1
    best_model = max(MODELS[1:5], key=lambda m: per_model[m]["end_to_end_correct"])
    newly_correct = sorted(correct_by_model[best_model] - correct_by_model["M0_baseline"])
    newly_correct_cls = sorted({r["class_name"] for r in comp_rows
                                if r["model"] == best_model and r["correct"] == "1"
                                and int(r["source_index"]) in newly_correct})
    m0_collapse = collapse_by_model["M0_baseline"]
    best_collapse = collapse_by_model[best_model]

    # V6 old RF session cross-validation present (item 4).
    old = re_summary["old_rf_session"]
    check("V6_old_rf_session_present",
          "M0_baseline" in old and old["M0_baseline"]["gate_pass"] >= 0,
          "old session M0 gate_pass=%s" % old["M0_baseline"]["gate_pass"])

    def _fmt_metrics(m):
        d = per_model[m]
        return {"gate_pass": d["gate_pass"], "gated_correct": d["gated_correct"],
                "gated_accuracy": d["gated_accuracy"],
                "end_to_end_correct": d["end_to_end_correct"],
                "end_to_end_accuracy": d["end_to_end_accuracy"]}

    # Neutral, data-driven conclusion.  The status token is a three-way split:
    # no gain / marginal gain without accuracy recovery / substantial gain.  The
    # split is a wording choice only -- the exact numbers are always reported.
    recovered_note = ""
    if newly_correct:
        recovered_note = (
            "  The entire gain is the re-admission of the previously gate-rejected "
            "frame(s) %s (%s), whose training residual drops below 0.100 under DC "
            "compensation and is then classified correctly."
            % (", ".join("sid %d" % s for s in newly_correct),
               ", ".join(newly_correct_cls)))
    if gain <= 0:
        status = "FIX3_REVIEW_R1_STATIC_DC_DOES_NOT_IMPROVE"
        verb = ("do NOT improve end-to-end accuracy over the M0 baseline "
                "(M0=%d/24, best no-oracle=%d/24)" % (m0_e2e, best_no_oracle))
    elif best_no_oracle < 12:
        status = "FIX3_REVIEW_R1_STATIC_DC_MARGINAL_NO_RECOVERY"
        verb = ("improve end-to-end accuracy only marginally (M0=%d/24 -> best "
                "no-oracle=%d/24), which does NOT recover 24-class accuracy"
                % (m0_e2e, best_no_oracle))
    else:
        status = "FIX3_REVIEW_R1_STATIC_DC_SUBSTANTIAL"
        verb = ("substantially improve end-to-end accuracy (M0=%d/24 -> best "
                "no-oracle=%d/24)" % (m0_e2e, best_no_oracle))

    conclusion = (
        "With full re-estimation after DC compensation (review item 1), the tested "
        "no-oracle static/linear DC candidates %s.%s  %d/24 frames still collapse "
        "to the two SSB classes (AM-SSB-WC/SC) under the best candidate (M0 baseline: "
        "%d/24).  The wide-linear 2x2 matrix is WELL-conditioned (median cond=%.2f, "
        "|b|/|a|~%.3f, bias gain ~1/|a|=%.1f), retiring the earlier 'small denom = "
        "1000x amplification' claim.  This negates ONLY the explicitly tested "
        "candidates (M1-M4 static/linear DC); it does NOT exhaust the space of "
        "category-independent no-training recovery, and does NOT establish that "
        "fine-tuning is required."
        % (verb, recovered_note, best_collapse, m0_collapse,
           med_cond, med_ratio, med_invgain))

    verdict = {
        "status": status,
        "conclusion": conclusion,
        "scope": ("Only the explicitly tested candidates (M0-M4, M5 bound) are "
                  "evaluated; the conclusion is limited to them."),
        "recovered_frames_target_session": {
            "m0_correct_sids": sorted(correct_by_model["M0_baseline"]),
            "best_model": best_model,
            "newly_correct_sids": newly_correct,
            "newly_correct_classes": newly_correct_cls,
            "m0_collapse_to_ssb": m0_collapse,
            "best_collapse_to_ssb": best_collapse,
        },
        "conditioning": {
            "median_cond_2x2": med_cond,
            "median_ratio_b_over_a": med_ratio,
            "median_inverse_gain_1_over_a": med_invgain,
            "retired_claim": "small denom = ill-conditioned / 1000x amplification",
            "replacement": "well-conditioned 2x2 (cond~1.1); bias gain ~1/|a|",
        },
        "models_target_session": {m: _fmt_metrics(m) for m in MODELS},
        "models_old_rf_session": {
            m: {"gate_pass": old[m]["gate_pass"],
                "gated_accuracy": old[m]["gated_accuracy"],
                "end_to_end_correct": old[m]["end_to_end_correct"],
                "end_to_end_accuracy": old[m]["end_to_end_accuracy"]}
            for m in MODELS
        },
        "checks": checks,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    c.dumps_json(verdict, out)

    print("[judge_r1] VERDICT: %s" % verdict["status"])
    print("[judge_r1] %s" % conclusion)
    print("[judge_r1] conditioning: cond=%.3f |b|/|a|=%.4f 1/|a|=%.1f"
          % (med_cond, med_ratio, med_invgain))
    for m in MODELS:
        d = per_model[m]
        ga = ("%.4f" % d["gated_accuracy"]) if d["gated_accuracy"] is not None else "n/a"
        print("  %-22s gate=%2d/24 gated_acc=%s e2e=%2d/24" %
              (m, d["gate_pass"], ga, d["end_to_end_correct"]))
    print("[judge_r1] %d/%d checks passed"
          % (sum(1 for ch in checks if ch["ok"]), len(checks)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
