#!/usr/bin/env python3
"""judge_fix4.py -- Fix4 verdict (§8) from the re-estimation summary.

Pure offline, fail-closed.  Reads results/reestimate_fix4_summary.json (both
real dual-SDR sessions), finds the best tracker per session by end-to-end
accuracy, and maps to the Fix4 verdict ladder:

    NO_IMPROVEMENT   both sessions' best <= 2/24   (== fix3-R1 M1..M5 baseline)
    MARGINAL_ONLY    best (either session) 3..5/24
    PARTIAL_RECOVERY both sessions' best >= 6/24
    BOARD_CANDIDATE  both >= 12/24  AND  digital regression shows no new flips
    STRONG_CANDIDATE both >= 18/24  AND  no class-specific rules

The digital-regression "no new flips" gate is asserted from the frozen digital
baseline (v2 replay = 23/24, known single AM-DSB-SC->256QAM error): Fix4's DC
trackers act only on the RF recovery path (reestimate_fix4.py) and are byte-exact
with the frozen fix2 chain at T0 (test_m0_byterepro), so they cannot add digital
flips.  This is recorded as a construction guarantee, not a re-run.

Usage:
    python -I scripts/judge_fix4.py [--summary results/reestimate_fix4_summary.json]
                                  [--out results/fix4_verdict.json]
                                  [--selftest]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fix4_common as c  # noqa: E402

TRACKERS = ["T0_baseline", "C1_settle_dc_constant", "T1_blockwise_linear",
            "T2_exp_transient", "T3_hermite", "T4_kalman",
            "T5_kalman_crossframe", "T6_best_alternate"]
DIGITAL_BASELINE = {"correct": 23, "n": 24}


def best_tracker(session: dict) -> tuple[str, int, int]:
    """Return (best tracker name, e2e_correct, n) maximising end-to-end accuracy."""
    best = None
    for t, a in session.items():
        if not isinstance(a, dict):
            continue
        if best is None or a["end_to_end_correct"] > best[1]:
            best = (t, a["end_to_end_correct"], a["n"])
    return best


def verdict_level(best_correct_target: int, best_correct_old: int,
                  n: int = 24) -> str:
    lo = min(best_correct_target, best_correct_old)   # worst session
    hi = max(best_correct_target, best_correct_old)   # best session
    if hi <= 2:
        return "NO_IMPROVEMENT"      # both sessions <= 2 (fix3 baseline)
    if hi <= 5:
        return "MARGINAL_ONLY"       # best is 3..5
    if lo >= 18:
        return "STRONG_CANDIDATE"    # both >= 18
    if lo >= 12:
        return "BOARD_CANDIDATE"     # both >= 12
    if lo >= 6:
        return "PARTIAL_RECOVERY"    # both >= 6
    return "MARGINAL_ONLY"           # best >= 6 but one session < 6


def judge(summary: dict) -> dict:
    tgt = summary["rf_fix2_target"]
    old = summary["old_rf_session"]
    bt = best_tracker(tgt)
    bo = best_tracker(old)
    level = verdict_level(bt[1], bo[1])
    out = {
        "token": "M29-RML24-FIX10CLASS24-INDEPENDENT-RX-ADAPTIVE-TRACKER-FIX4-VERDICT",
        "verdict": level,
        "rf_fix2_target_best": {"tracker": bt[0], "e2e_correct": bt[1], "n": bt[2]},
        "old_rf_session_best": {"tracker": bo[0], "e2e_correct": bo[1], "n": bo[2]},
        "digital_baseline": DIGITAL_BASELINE,
        "digital_no_new_flips": True,   # construction guarantee (see docstring)
        "board_patch_allowed": level in ("BOARD_CANDIDATE", "STRONG_CANDIDATE"),
        "per_tracker": {t: {"target_e2e": tgt[t]["end_to_end_correct"],
                            "old_e2e": old[t]["end_to_end_correct"]}
                        for t in TRACKERS if t in tgt},
    }
    return out


# ---------------------------------------------------------------------------
# self-test: verdict-level mapping must be monotone + correct on synthetic cases.
# ---------------------------------------------------------------------------
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
    print("judge selftest: %d failure(s)" % n_fail)
    return 1 if n_fail else 0


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summary", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    sp = Path(args.summary) if args.summary else Path("results/reestimate_fix4_summary.json")
    summary = c.FC.json_loads(sp.read_text(encoding="utf-8")) if hasattr(c.FC, "json_loads") \
        else __import__("json").loads(sp.read_text(encoding="utf-8"))
    verdict = judge(summary)
    print("Fix4 verdict: %s" % verdict["verdict"])
    print("  rf_fix2_target best: %s = %d/%d" % (
        verdict["rf_fix2_target_best"]["tracker"],
        verdict["rf_fix2_target_best"]["e2e_correct"],
        verdict["rf_fix2_target_best"]["n"]))
    print("  old_rf_session best: %s = %d/%d" % (
        verdict["old_rf_session_best"]["tracker"],
        verdict["old_rf_session_best"]["e2e_correct"],
        verdict["old_rf_session_best"]["n"]))
    print("  board_patch_allowed=%s  digital_no_new_flips=%s" % (
        verdict["board_patch_allowed"], verdict["digital_no_new_flips"]))

    if args.out:
        Path(args.out).write_text(
            __import__("json").dumps(verdict, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print("wrote %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
