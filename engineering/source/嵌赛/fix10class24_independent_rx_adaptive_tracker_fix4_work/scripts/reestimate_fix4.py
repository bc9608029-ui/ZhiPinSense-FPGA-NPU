#!/usr/bin/env python3
"""reestimate_fix4.py -- adaptive DC/LO-drift trackers, full re-estimation.

Fix4 = M29-RML24-FIX10CLASS24-INDEPENDENT-RX-ADAPTIVE-TRACKER-FIX4.  Pure offline.

For every frame of the two real dual-SDR RF captures, and for every tracker
(T0..T6, plus the fix3-R1 C1 settle-DC anchor for cross-check):

    load raw burst -> align (est0 timing) -> tracker DC trajectory d[n]
    -> map d[n] back to RAW coordinates (np.roll +timing; fixes fix3's latent
       "DC not rolled back" bug) -> subtract -> RE-ESTIMATE the full fix2 chain
       (timing/CFO/tau/a/b/residual) -> recompute the 0.100 gate -> recover
       -> Host BF16 classify -> report gate_pass/24, gated_acc, e2e/24.

All trackers read ONLY the 4 public reference blocks; none read the unknown
payload / class / label / logits to choose parameters (trackers_fix4.py).

T6 = best-of(T1..T4) by public training residual, then alternating re-estimation
     (cumulative DC refinement, <=3 rounds).  T5 (cross-frame Kalman) carries its
     own prior state across the capture-order frame sequence.

Usage:
    python -I scripts/reestimate_fix4.py \
        --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244 \
        --old-capture-dir F:/嵌赛/board_capture/rml24_independent_v2_dual_1773374217_210 \
        --model-dir F:/嵌赛/.../model_rml24_bf16 \
        --icraft-run D:/icraft/bin/icraft-run.exe \
        --out-dir results \
        [--no-infer] [--max-frames N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fix4_common as c
import fix3_recovery as R
import trackers_fix4 as TK

GATE = c.GATE

# Trackers evaluated per frame.  C1 is the fix3-R1 M1 anchor (cross-check only).
TRACKER_LIST = ["T0_baseline", "C1_settle_dc_constant",
                "T1_blockwise_linear", "T2_exp_transient", "T3_hermite",
                "T4_kalman", "T5_kalman_crossframe", "T6_best_alternate"]

# T6 selects among the intra-frame trackers (T5's cross-frame gain is separate).
SELECTABLE_T6 = ["T1_blockwise_linear", "T2_exp_transient", "T3_hermite", "T4_kalman"]
MAX_ALT = 3

# DC trajectory observability key points (aligned coords).
DC_KEYS = [("settle", (R.SETTLE_START + R.SETTLE_END) / 2.0),
           ("train", (R.TRAIN_START + R.TRAIN_END) / 2.0),
           ("payload_start", float(R.PAYLOAD_START)),
           ("payload_mid", (R.PAYLOAD_START + R.PAYLOAD_END) / 2.0),
           ("payload_end", float(R.PAYLOAD_END)),
           ("guard", (R.GUARD_START + R.GUARD_END) / 2.0),
           ("tail", (R.TAIL_START + R.TAIL_END) / 2.0)]


def _subtract_dc(raw: np.ndarray, dc_aligned: np.ndarray, timing: int) -> np.ndarray:
    """Map a DC trajectory in aligned coords back to raw coords and subtract."""
    dc_raw = np.roll(dc_aligned, int(timing)) if timing else dc_aligned
    return raw - dc_raw


def run_tracker(raw: np.ndarray, est0: dict, name: str, sid: int, cls: int,
                icraft_run, model_json, model_raw, no_infer: bool,
                prior=None) -> tuple[dict, np.ndarray, dict]:
    """Run one tracker for one frame.  Returns (result_dict, dc_aligned, state)."""
    timing0 = int(est0["timing_offset"])

    if name == "T0_baseline":
        est2 = est0
        rec = R.recover_v2(raw, est2)
        dc_aligned = np.zeros(len(raw), dtype=np.complex128)
        state = None
    elif name == "T6_best_alternate":
        est2, rec, dc_aligned, state = _run_t6(raw, est0, timing0)
    else:
        aligned = R.aligned_burst(raw, est0)
        dc_aligned, state = TK.dc_trajectory(name, aligned, prior)
        raw_dc = _subtract_dc(raw, dc_aligned, timing0)
        est2 = R.estimate_public_reference_fix2(raw_dc)
        rec = R.recover_v2(raw_dc, est2)

    gated = 1 if est2["training_residual_rel"] <= GATE else 0
    pred = -1
    if gated and not no_infer:
        pred = int(np.argmax(R.run_host_infer(icraft_run, model_json, model_raw, rec)))
    correct = 1 if pred == cls else 0
    return {"sid": sid, "cls": cls, "est": est2, "rec": rec,
            "gated": gated, "pred": pred, "correct": correct}, dc_aligned, state


def _run_t6(raw: np.ndarray, est0: dict, timing0: int):
    """T6: best-of(T1..T4) by public training residual, then alternating (<=3).

    Returns (est2, recovered_model_input, dc_total_aligned, None).  The caller
    (run_tracker) does the gate + classification so there is no double inference.
    """
    # seed round: try each selectable tracker on the raw burst.
    best = None  # (resid, tracker_name, dc_total, est)
    for t in SELECTABLE_T6:
        aligned = R.aligned_burst(raw, est0)
        dc_al, _ = TK.dc_trajectory(t, aligned, None)
        dc_total = np.roll(dc_al, timing0) if timing0 else dc_al
        est = R.estimate_public_reference_fix2(raw - dc_total)
        r = est["training_residual_rel"]
        if best is None or r < best[0]:
            best = (r, t, dc_total, est)

    resid, t_best, dc_total, est_best = best
    # alternating cumulative DC refinement.
    for _ in range(MAX_ALT - 1):
        residual_burst = raw - dc_total
        aligned = R.aligned_burst(residual_burst, est_best)
        dc_al, _ = TK.dc_trajectory(t_best, aligned, None)
        dcb = int(est_best["timing_offset"])
        dc_res = np.roll(dc_al, dcb) if dcb else dc_al
        new_est = R.estimate_public_reference_fix2(raw - (dc_total + dc_res))
        if new_est["training_residual_rel"] < resid:
            resid = new_est["training_residual_rel"]
            dc_total = dc_total + dc_res
            est_best = new_est
        else:
            break

    rec = R.recover_v2(raw - dc_total, est_best)
    return est_best, rec, dc_total, None


def process_session(name: str, capture_dir: Path, results: list[dict],
                    model_dir: Path, icraft_run: Path, out_dir: Path,
                    no_infer: bool, max_frames: int, trackers: list[str]) -> dict:
    model_json = model_dir / "rml24_adamrv11_bf16.json"
    model_raw = model_dir / "rml24_adamrv11_bf16.raw"
    if c.FC.sha256_file(model_json) != c.FROZEN_MODEL_JSON_SHA256:
        c.FC.fail("model json SHA mismatch")
    if c.FC.sha256_file(model_raw) != c.FROZEN_MODEL_RAW_SHA256:
        c.FC.fail("model raw SHA mismatch")

    frames = []
    for r in results[:max_frames]:
        sid = int(r["source_index"])
        cls = int(r["class_index"])
        raw, _ = R.load_burst(capture_dir, sid)
        est0 = R.estimate_public_reference_fix2(raw)
        frames.append({"r": r, "sid": sid, "cls": cls, "raw": raw, "est0": est0})

    comp_header = ["tracker", "source_index", "class_index", "class_name",
                   "timing_offset", "coarse_cfo_hz", "fractional_timing",
                   "a_mag", "b_mag", "training_residual", "training_residual_rel",
                   "gated", "pred", "correct",
                   "recovered_dc_re", "recovered_dc_im"]
    comp_rows = []
    dc_header = ["tracker", "source_index"] + [k for k, _ in DC_KEYS] + ["unit"]
    dc_rows = []
    agg = {t: {"gate_pass": 0, "gated_correct": 0, "e2e_correct": 0, "n": 0}
           for t in trackers}

    for t in trackers:
        prior = None  # cross-frame prior for T5
        for fr in frames:
            out, dc_aligned, state = run_tracker(
                fr["raw"], fr["est0"], t, fr["sid"], fr["cls"],
                icraft_run, model_json, model_raw, no_infer, prior=prior)
            if t == "T5_kalman_crossframe":
                prior = state
            agg[t]["n"] += 1
            agg[t]["gate_pass"] += out["gated"]
            if out["gated"]:
                agg[t]["gated_correct"] += out["correct"]
            agg[t]["e2e_correct"] += out["correct"]
            est = out["est"]
            rec = out["rec"]
            comp_rows.append([
                t, fr["sid"], fr["cls"], c.FC.LABELS[fr["cls"]],
                str(est["timing_offset"]), "%.2f" % est["coarse_cfo_hz"],
                "%.3f" % est["fractional_timing"],
                "%.6f" % abs(est["a"]), "%.6f" % abs(est["b"]),
                "%.6f" % est["training_residual"],
                "%.6f" % est["training_residual_rel"], out["gated"], out["pred"],
                out["correct"], "%.4f" % rec.mean().real, "%.4f" % rec.mean().imag,
            ])
            if dc_aligned is not None:
                row = [t, fr["sid"]]
                for _, idx in DC_KEYS:
                    v = complex(dc_aligned[min(int(idx), len(dc_aligned) - 1)])
                    row += ["%.5f" % v.real, "%.5f" % v.imag]
                row.append("aligned")
                dc_rows.append(row)

    prefix = "reestimate_%s" % name
    c.FC.write_tsv(out_dir / (prefix + "_comparison.tsv"), comp_header, comp_rows)
    dc_header = ["tracker", "source_index"]
    for k, _ in DC_KEYS:
        dc_header += ["%s_re" % k, "%s_im" % k]
    dc_header.append("unit")
    c.FC.write_tsv(out_dir / (prefix + "_dc_trajectory.tsv"), dc_header, dc_rows)

    summary = {}
    for t in trackers:
        a = agg[t]
        summary[t] = {
            "gate_pass": a["gate_pass"], "n": a["n"],
            "gate_pass_frac": a["gate_pass"] / a["n"] if a["n"] else 0.0,
            "gated_correct": a["gated_correct"],
            "gated_accuracy": (a["gated_correct"] / a["gate_pass"]
                               if a["gate_pass"] else None),
            "end_to_end_correct": a["e2e_correct"],
            "end_to_end_accuracy": a["e2e_correct"] / a["n"] if a["n"] else 0.0,
        }
    return summary


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture-dir", required=True)
    ap.add_argument("--old-capture-dir", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--icraft-run", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--no-infer", action="store_true")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--trackers", default=None,
                    help="comma-separated tracker subset (default: all)")
    args = ap.parse_args(argv)

    capture_dir = Path(args.capture_dir)
    old_capture_dir = Path(args.old_capture_dir)
    model_dir = Path(args.model_dir)
    icraft_run = Path(args.icraft_run)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mf = args.max_frames if args.max_frames > 0 else 24
    if args.trackers:
        trackers = [t.strip() for t in args.trackers.split(",") if t.strip()]
        unknown = [t for t in trackers if t not in TRACKER_LIST]
        if unknown:
            c.FC.fail("unknown tracker(s): %s" % ",".join(unknown))
    else:
        trackers = list(TRACKER_LIST)

    target_results = c.FC.load_results_tsv(capture_dir / "board_independent_rx_results.tsv")
    _, old_rows = c.FC.read_tsv(old_capture_dir / "board_independent_rx_results.tsv")
    old_results = [{"source_index": int(r["source_index"]),
                    "class_index": int(r["class_index"])} for r in old_rows]

    summaries = {}
    summaries["rf_fix2_target"] = process_session(
        "fix2_target", capture_dir, target_results, model_dir, icraft_run,
        out_dir, args.no_infer, mf, trackers)
    summaries["old_rf_session"] = process_session(
        "old_rf_v1v2", old_capture_dir, old_results, model_dir, icraft_run,
        out_dir, args.no_infer, mf, trackers)

    c.FC.dumps_json(summaries, out_dir / "reestimate_fix4_summary.json")

    for sess, sm in summaries.items():
        print("[reestimate_fix4] %s:" % sess)
        for t in trackers:
            a = sm[t]
            print("  %-22s gate=%2d/24  gated_acc=%s  e2e=%2d/24 (%.4f)" % (
                t, a["gate_pass"],
                ("%.4f" % a["gated_accuracy"]) if a["gated_accuracy"] is not None
                else "n/a",
                a["end_to_end_correct"], a["end_to_end_accuracy"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
