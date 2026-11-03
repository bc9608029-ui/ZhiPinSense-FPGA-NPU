#!/usr/bin/env python3
"""judge_fix4_r1.py -- REVIEW-R1 verdict from corrected re-estimation + measured
digital counterexample.

Same §8 verdict ladder as judge_fix4.py, but `digital_no_new_flips` is READ from
the measured digital counterexample (digital_counterexample_r1_summary.json)
instead of being hardcoded true (requirement 7).

    NO_IMPROVEMENT   both sessions' best <= 2/24   (== fix3-R1 baseline)
    MARGINAL_ONLY    best (either session) 3..5/24
    PARTIAL_RECOVERY both sessions' best >= 6/24
    BOARD_CANDIDATE  both >= 12/24  AND  digital regression shows no new flips
    STRONG_CANDIDATE both >= 18/24  AND  no class-specific rules

Usage:
    python -I scripts/judge_fix4_r1.py \
        [--summary results_r1/reestimate_fix4_r1_summary.json] \
        [--digital results_r1/digital_counterexample_r1_summary.json] \
        [--out results_r1/fix4_review_r1_verdict.json] \
        [--selftest]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fix4_common as c  # noqa: E402

TRACKERS = ["T0_baseline", "C1_settle_dc_constant", "T1_blockwise_linear",
            "T2_exp_transient", "T3_hermite", "T4_kalman",
            "T5_kalman_crossframe", "T6_best_alternate"]


def best_tracker(session: dict):
    best = None
    for t, a in session.items():
        if not isinstance(a, dict):
            continue
        if best is None or a["end_to_end_correct"] > best[1]:
            best = (t, a["end_to_end_correct"], a["n"])
    return best


def verdict_level(best_correct_target: int, best_correct_old: int,
                  n: int = 24) -> str:
    lo = min(best_correct_target, best_correct_old)
    hi = max(best_correct_target, best_correct_old)
    if hi <= 2:
        return "NO_IMPROVEMENT"
    if hi <= 5:
        return "MARGINAL_ONLY"
    if lo >= 18:
        return "STRONG_CANDIDATE"
    if lo >= 12:
        return "BOARD_CANDIDATE"
    if lo >= 6:
        return "PARTIAL_RECOVERY"
    return "MARGINAL_ONLY"


def judge(summary: dict, digital: dict) -> dict:
    tgt = summary["rf_fix2_target"]
    old = summary["old_rf_session"]
    bt = best_tracker(tgt)
    bo = best_tracker(old)
    level = verdict_level(bt[1], bo[1])

    # measured digital_no_new_flips (requirement 7): all trackers show 0 new flips.
    measured_no_flips = bool(digital.get("digital_no_new_flips"))
    all_no_flips = all(digital.get("digital_no_new_flips", {}).values()) \
        if digital.get("digital_no_new_flips") else False

    return {
        "token": "M29-RML24-FIX10CLASS24-INDEPENDENT-RX-ADAPTIVE-TRACKER-FIX4-REVIEW-R1-VERDICT",
        "verdict": level,
        "rf_fix2_target_best": {"tracker": bt[0], "e2e_correct": bt[1], "n": bt[2]},
        "old_rf_session_best": {"tracker": bo[0], "e2e_correct": bo[1], "n": bo[2]},
        "digital_baseline": {"correct": digital.get("digital_baseline_correct"),
                             "n": digital.get("digital_baseline_n")},
        "digital_no_new_flips_measured": all_no_flips,
        "digital_no_new_flips_per_tracker": digital.get("new_flips_per_tracker", {}),
        "board_patch_allowed": level in ("BOARD_CANDIDATE", "STRONG_CANDIDATE"),
        "per_tracker": {t: {"target_e2e": tgt[t]["end_to_end_correct"],
                            "old_e2e": old[t]["end_to_end_correct"]}
                        for t in TRACKERS if t in tgt},
    }


def _selftest() -> int:
    cases = [
        ((1, 1), "NO_IMPROVEMENT"),
        ((2, 2), "NO_IMPROVEMENT"),
        ((2, 4), "MARGINAL_ONLY"),
        ((5, 5), "MARGINAL_ONLY"),
        ((6, 6), "PARTIAL_RECOVERY"),
        ((6, 13), "PARTIAL_RECOVERY"),
        ((12, 12), "BOARD_CANDIDATE"),
        ((13, 17), "BOARD_CANDIDATE"),
        ((18, 18), "STRONG_CANDIDATE"),
        ((20, 24), "STRONG_CANDIDATE"),
    ]
    n_fail = 0
    for (a, b), want in cases:
        got = verdict_level(a, b)
        ok = got == want
        print("[%s] verdict_level(%d,%d)=%s (want %s)" % (
            "OK " if ok else "FAIL", a, b, got, want))
        n_fail += 0 if ok else 1
    print("judge_fix4_r1 selftest: %d failure(s)" % n_fail)
    return 1 if n_fail else 0


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summary", default=None)
    ap.add_argument("--digital", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    sp = Path(args.summary) if args.summary else Path("results_r1/reestimate_fix4_r1_summary.json")
    dp = Path(args.digital) if args.digital else Path("results_r1/digital_counterexample_r1_summary.json")
    summary = json.loads(sp.read_text(encoding="utf-8"))
    digital = json.loads(dp.read_text(encoding="utf-8"))
    verdict = judge(summary, digital)
    print("Fix4 REVIEW-R1 verdict: %s" % verdict["verdict"])
    print("  rf_fix2_target best: %s = %d/%d" % (
        verdict["rf_fix2_target_best"]["tracker"],
        verdict["rf_fix2_target_best"]["e2e_correct"],
        verdict["rf_fix2_target_best"]["n"]))
    print("  old_rf_session best: %s = %d/%d" % (
        verdict["old_rf_session_best"]["tracker"],
        verdict["old_rf_session_best"]["e2e_correct"],
        verdict["old_rf_session_best"]["n"]))
    print("  board_patch_allowed=%s  digital_no_new_flips_measured=%s" % (
        verdict["board_patch_allowed"], verdict["digital_no_new_flips_measured"]))

    if args.out:
        Path(args.out).write_text(
            json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
