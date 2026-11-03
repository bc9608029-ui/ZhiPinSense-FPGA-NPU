#!/usr/bin/env python3
"""summarize_fix4_results.py -- confusion matrix + candidate summary + tensor SHA.

Pure offline, fail-closed.  Reads the two per-session comparison TSVs written by
reestimate_fix4.py and, for the best tracker per session (tie-break by gated
accuracy then gate count), writes:

    results/fix4_confusion_matrix.tsv   (pred x true, per session, best tracker)
    results/fix4_candidate_summary.tsv  (per tracker e2e/gate/gated, both sessions)
    results/fix4_tensor_sha.tsv         (SHA256 of each recovered [2,1024] f32
                                         model-input tensor, best tracker only;
                                         recomputed deterministically, no infer)

The recovered tensor byte layout is identical to test_m0_byterepro (I-then-Q f32
LE), so this SHA is the board-side byte-exactness anchor.

Usage:
    python -I scripts/summarize_fix4_results.py \
        --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244 \
        --old-capture-dir F:/嵌赛/board_capture/rml24_independent_v2_dual_1773374217_210 \
        --model-dir F:/嵌赛/.../model_rml24_bf16 \
        --out-dir results
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fix4_common as c
import fix3_recovery as R
import trackers_fix4 as TK

TRACKERS = ["T0_baseline", "C1_settle_dc_constant", "T1_blockwise_linear",
            "T2_exp_transient", "T3_hermite", "T4_kalman",
            "T5_kalman_crossframe", "T6_best_alternate"]


def read_comparison(path: Path) -> list[dict]:
    _, rows = c.FC.read_tsv(path)   # read_tsv returns (header, dict rows)
    return rows


def per_tracker_agg(rows: list[dict]) -> dict:
    agg = {t: {"n": 0, "gate": 0, "gated_correct": 0, "e2e": 0} for t in TRACKERS}
    for r in rows:
        t = r["tracker"]
        a = agg[t]
        a["n"] += 1
        g = int(r["gated"])
        a["gate"] += g
        if g:
            a["gated_correct"] += int(r["correct"])
        a["e2e"] += int(r["correct"])
    return agg


def best_tracker(agg: dict) -> str:
    # max e2e; tie-break by gated_accuracy (correct/gate), then gate count.
    def key(t):
        a = agg[t]
        ga = a["gated_correct"] / a["gate"] if a["gate"] else -1.0
        return (a["e2e"], ga, a["gate"])
    return max(TRACKERS, key=key)


def confusion_matrix(rows: list[dict], tracker: str) -> np.ndarray:
    m = np.zeros((24, 24), dtype=int)
    for r in rows:
        if r["tracker"] != tracker:
            continue
        if not int(r["gated"]) or int(r["pred"]) < 0:
            continue
        m[int(r["pred"]), int(r["class_index"])] += 1
    return m


def tensor_sha(capture_dir: Path, results: list[dict], tracker: str) -> list[tuple]:
    out = []
    for r in results:
        sid = int(r["source_index"])
        cls = int(r["class_index"])
        raw, _ = R.load_burst(capture_dir, sid)
        est0 = R.estimate_public_reference_fix2(raw)
        timing0 = int(est0["timing_offset"])
        if tracker == "T0_baseline":
            rec = R.recover_v2(raw, est0)
        else:
            aligned = R.aligned_burst(raw, est0)
            dc_aligned, _ = TK.dc_trajectory(tracker, aligned, None)
            dc_raw = np.roll(dc_aligned, timing0) if timing0 else dc_aligned
            est2 = R.estimate_public_reference_fix2(raw - dc_raw)
            rec = R.recover_v2(raw - dc_raw, est2)
        x = np.empty((2, len(rec)), dtype="<f4")
        x[0] = rec.real.astype("<f4")
        x[1] = rec.imag.astype("<f4")
        h = hashlib.sha256(x.tobytes()).hexdigest()
        out.append((tracker, sid, cls, len(x.tobytes()), h))
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture-dir", required=True)
    ap.add_argument("--old-capture-dir", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    cap = Path(args.capture_dir)
    old = Path(args.old_capture_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if c.FC.sha256_file(Path(args.model_dir) / "rml24_adamrv11_bf16.json") != c.FROZEN_MODEL_JSON_SHA256:
        c.FC.fail("model json SHA mismatch")
    if c.FC.sha256_file(Path(args.model_dir) / "rml24_adamrv11_bf16.raw") != c.FROZEN_MODEL_RAW_SHA256:
        c.FC.fail("model raw SHA mismatch")

    tgt_rows = read_comparison(out / "reestimate_fix2_target_comparison.tsv")
    old_rows = read_comparison(out / "reestimate_old_rf_v1v2_comparison.tsv")
    tgt_agg = per_tracker_agg(tgt_rows)
    old_agg = per_tracker_agg(old_rows)
    tgt_best = best_tracker(tgt_agg)
    old_best = best_tracker(old_agg)

    # candidate summary
    cand_header = ["session", "tracker", "gate_pass", "n", "gated_correct",
                   "gated_accuracy", "end_to_end_correct", "end_to_end_accuracy"]
    cand_rows = []
    for sess, agg in [("rf_fix2_target", tgt_agg), ("old_rf_session", old_agg)]:
        for t in TRACKERS:
            a = agg[t]
            cand_rows.append([sess, t, str(a["gate"]), str(a["n"]),
                              str(a["gated_correct"]),
                              ("%.6f" % (a["gated_correct"] / a["gate"])) if a["gate"] else "n/a",
                              str(a["e2e"]), "%.6f" % (a["e2e"] / a["n"])])
    c.FC.write_tsv(out / "fix4_candidate_summary.tsv", cand_header, cand_rows)

    # confusion matrix (best tracker per session; T0 added as reference row block)
    def cm_rows(sess, rows, agg):
        out_rows = []
        for tracker in [tgt_best if sess == "rf_fix2_target" else old_best, "T0_baseline"]:
            m = confusion_matrix(rows, tracker)
            for true in range(24):
                for pred in range(24):
                    if m[pred, true]:
                        out_rows.append([sess, tracker, str(pred), str(true),
                                         c.FC.LABELS[pred], c.FC.LABELS[true],
                                         str(m[pred, true])])
        return out_rows
    cm_rows = cm_rows("rf_fix2_target", tgt_rows, tgt_agg) \
        + cm_rows("old_rf_session", old_rows, old_agg)
    c.FC.write_tsv(out / "fix4_confusion_matrix.tsv",
                   ["session", "tracker", "pred", "true", "pred_label", "true_label", "count"],
                   cm_rows)

    # tensor SHA (best tracker only)
    tgt_results = [{"source_index": int(r["source_index"]),
                    "class_index": int(r["class_index"])}
                   for r in tgt_rows if r["tracker"] == tgt_best]
    # dedupe by source_index (one row per frame for a given tracker)
    seen = set()
    tgt_results = [r for r in tgt_results if not (r["source_index"] in seen or seen.add(r["source_index"]))]
    old_results = [{"source_index": int(r["source_index"]),
                    "class_index": int(r["class_index"])}
                   for r in old_rows if r["tracker"] == old_best]
    seen = set()
    old_results = [r for r in old_results if not (r["source_index"] in seen or seen.add(r["source_index"]))]

    sha_rows = []
    for label, cdir, results, tracker in [("rf_fix2_target", cap, tgt_results, tgt_best),
                                          ("old_rf_session", old, old_results, old_best)]:
        for (tracker_, sid, cls, nbytes, h) in tensor_sha(cdir, results, tracker):
            sha_rows.append([label, tracker_, str(sid), str(cls), str(nbytes), h])
    c.FC.write_tsv(out / "fix4_tensor_sha.tsv",
                   ["session", "tracker", "source_index", "class_index", "nbytes", "sha256"],
                   sha_rows)

    print("best tracker rf_fix2_target = %s (e2e %d/24)" % (
        tgt_best, tgt_agg[tgt_best]["e2e"]))
    print("best tracker old_rf_session = %s (e2e %d/24)" % (
        old_best, old_agg[old_best]["e2e"]))
    print("wrote candidate summary / confusion matrix / tensor SHA to %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
