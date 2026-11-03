#!/usr/bin/env python3
"""reestimate_fix3_r1.py -- FIX3-REVIEW-R1: full re-estimation after DC compensation.

The prior Phase C was methodologically flawed (accepted in review): every candidate
re-used the PRE-CORRECTION CFO/timing/a/b/residual, and the gate was copied from
fr["gated"] instead of recomputed.  This script fixes that:

  for each candidate DC model M:
      load raw burst -> align (timing) -> estimate silence DC -> subtract DC
      -> RE-ESTIMATE timing + CFO + tau + a/b + residual (full fix2 chain)
      -> recompute gate (residual_rel <= 0.100) -> recover -> Host classify
      -> report gate_pass/24, gated_correct/gate_pass, end_to_end_correct/24.

Models (all category-independent; M1-M4 read ONLY the silence regions):
  M0 baseline        no DC removal.
  M1 settle-DC       subtract settling-zero [1024:2048] mean (constant).
  M2 guard-DC        subtract guard-zero [56832:58880] mean (constant).
  M3 settle+guard    subtract the average of the two silence means (constant).
  M4 linear-drift    per-sample bounded linear ramp settle->guard (TRUE drift).
  M5 payload-mean    subtract the whole-payload mean (constant) -- DIAGNOSTIC
                     UPPER BOUND ONLY: reads payload IQ, forbidden in production;
                     it is a CONSTANT, NOT a time-varying oracle.

Also emits, replacing the "small denom = ill-conditioned" narrative (item 5):
  |a|, |b|, |b|/|a|, condition number of the 2x2 wide-linear matrix, denom,
  effective (post-equalization) signal power, post-eq SNR, and the recovered
  DC relative to the recovered signal -- plus the honest bias-gain ~1/|a|.

And cross-validates the OLD RF session (item 4) with the same re-estimation.

Usage:
    python -I scripts/reestimate_fix3_r1.py \
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

import fix3_common as c
import fix3_recovery as R

# Import the frozen contract (for the training-block reference RMS).
_CONTRACT_DIR = r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts"
if _CONTRACT_DIR not in sys.path:
    sys.path.insert(0, _CONTRACT_DIR)
import radioml_independent_rx_contract as IRX  # noqa: E402

MODELS = ["M0_baseline", "M1_settle_dc", "M2_guard_dc",
          "M3_settle_guard_avg", "M4_linear_drift", "M5_payload_mean_bound"]

GATE = c.GATE_THRESHOLD


# ---------------------------------------------------------------------------
# DC models: return a per-sample complex DC in RAW coordinates (len == raw).
# ---------------------------------------------------------------------------
def dc_samples(model: str, raw: np.ndarray, aligned: np.ndarray,
               timing: int) -> np.ndarray:
    """Per-sample DC (complex) in raw coordinates.  M1-M4 read only silence."""
    n = len(raw)
    if model == "M0_baseline":
        return np.zeros(n, dtype=np.complex128)

    settle = complex(aligned[R.SETTLE_START:R.SETTLE_END].mean())
    guard = complex(aligned[R.GUARD_START:R.GUARD_END].mean())

    if model == "M1_settle_dc":
        return np.full(n, settle, dtype=np.complex128)
    if model == "M2_guard_dc":
        return np.full(n, guard, dtype=np.complex128)
    if model == "M3_settle_guard_avg":
        return np.full(n, (settle + guard) / 2.0, dtype=np.complex128)
    if model == "M4_linear_drift":
        # True per-sample bounded drift: linear ramp anchored at the two silence
        # region centers, extrapolated (bounded) across the whole burst.
        t_s = (R.SETTLE_START + R.SETTLE_END) / 2.0
        t_g = (R.GUARD_START + R.GUARD_END) / 2.0
        slope = (guard - settle) / (t_g - t_s)
        nn = np.arange(n, dtype=np.float64)                 # aligned coords
        ramp_aligned = settle + slope * (nn - t_s)
        return np.roll(ramp_aligned, timing)                # map to raw coords
    if model == "M5_payload_mean_bound":
        return np.full(n, complex(aligned[R.PAYLOAD_START:R.PAYLOAD_END].mean()),
                       dtype=np.complex128)
    raise ValueError(model)


# ---------------------------------------------------------------------------
# Wide-linear matrix condition number (item 5).
# ---------------------------------------------------------------------------
def wide_linear_cond(a: complex, b: complex) -> float:
    """Condition number of the real 2x2 matrix M for r = a*x + b*conj(x).

    M = [[a_I+b_I, b_Q-a_Q],
         [a_Q+b_Q, a_I-b_I]]   (maps [x_I,x_Q] -> [r_I,r_Q])
    det(M) = |a|^2 - |b|^2 = denom.  cond = sigma_max/sigma_min.
    """
    aI, aQ = a.real, a.imag
    bI, bQ = b.real, b.imag
    M = np.array([[aI + bI, bQ - aQ], [aQ + bQ, aI - bI]], dtype=np.float64)
    sv = np.linalg.svd(M, compute_uv=False)
    return float(sv[0] / sv[1]) if sv[1] > 1e-300 else float("inf")


def condition_row(r: dict, est: dict, rec: np.ndarray) -> list[str]:
    """One row of the condition-number / post-eq metrics table."""
    a, b = est["a"], est["b"]
    a_mag, b_mag = abs(a), abs(b)
    denom = a_mag ** 2 - b_mag ** 2
    cond = wide_linear_cond(a, b)
    inv_gain = 1.0 / a_mag if a_mag > 1e-300 else float("inf")
    # effective (post-equalization) signal power = |a| * training-block RMS
    train_rms = float(np.sqrt(np.mean(np.abs(IRX.payload_training_complex()) ** 2)))
    post_eq_signal = a_mag * train_rms
    post_eq_noise = float(est["training_residual"])
    post_eq_snr_db = (20.0 * np.log10(post_eq_signal / post_eq_noise)
                      if post_eq_noise > 1e-300 else float("inf"))
    rec_rms = float(np.sqrt(np.mean(np.abs(rec) ** 2)))
    rec_dc = complex(rec.mean())
    dc_over_signal = abs(rec_dc) / rec_rms if rec_rms > 1e-300 else float("inf")
    return [
        str(int(r["source_index"])), c.LABELS[int(r["class_index"])],
        "%.6f" % a_mag, "%.6f" % b_mag, "%.5f" % (b_mag / a_mag if a_mag > 1e-300 else float("inf")),
        "%.4f" % cond, "%.7f" % denom, "%.2f" % inv_gain,
        "%.4f" % post_eq_signal, "%.4f" % post_eq_noise, "%.2f" % post_eq_snr_db,
        "%.4f" % rec_dc.real, "%.4f" % rec_dc.imag, "%.4f" % abs(rec_dc),
        "%.4f" % dc_over_signal, "%.4f" % rec_rms,
    ]


# ---------------------------------------------------------------------------
# One candidate's full re-estimation for one frame.
# ---------------------------------------------------------------------------
def run_candidate(raw: np.ndarray, est0: dict, model: str, sid: int, cls: int,
                  icraft_run: Path, model_json: Path, model_raw: Path,
                  no_infer: bool) -> dict:
    aligned = R.aligned_burst(raw, est0)
    dc = dc_samples(model, raw, aligned, int(est0["timing_offset"]))
    raw_dc = raw - dc
    est2 = R.estimate_public_reference_fix2(raw_dc)
    rec = R.recover_v2(raw_dc, est2)
    gated = 1 if est2["training_residual_rel"] <= GATE else 0
    pred = -1
    if gated and not no_infer:
        pred = int(np.argmax(R.run_host_infer(icraft_run, model_json, model_raw, rec)))
    correct = 1 if pred == cls else 0
    return {"sid": sid, "cls": cls, "est": est2, "rec": rec,
            "gated": gated, "pred": pred, "correct": correct}


def process_session(name: str, capture_dir: Path, results: list[dict],
                    model_dir: Path, icraft_run: Path, out_dir: Path,
                    no_infer: bool, max_frames: int) -> dict:
    model_json = model_dir / "rml24_adamrv11_bf16.json"
    model_raw = model_dir / "rml24_adamrv11_bf16.raw"
    if c.sha256_file(model_json) != c.FROZEN_MODEL_JSON_SHA256:
        c.fail("model json SHA mismatch")
    if c.sha256_file(model_raw) != c.FROZEN_MODEL_RAW_SHA256:
        c.fail("model raw SHA mismatch")

    frames = []
    for r in results[:max_frames]:
        sid = int(r["source_index"])
        cls = int(r["class_index"])
        raw, _ = R.load_burst(capture_dir, sid)
        est0 = R.estimate_public_reference_fix2(raw)
        frames.append({"r": r, "sid": sid, "cls": cls, "raw": raw, "est0": est0})

    comp_header = ["model", "source_index", "class_index", "class_name",
                   "timing_offset", "coarse_cfo_hz", "fractional_timing",
                   "a_mag", "b_mag", "training_residual_rel", "gated", "pred",
                   "correct", "recovered_dc_re", "recovered_dc_im"]
    comp_rows = []
    agg = {m: {"gate_pass": 0, "gated_correct": 0, "e2e_correct": 0, "n": 0}
           for m in MODELS}

    for m in MODELS:
        for fr in frames:
            out = run_candidate(fr["raw"], fr["est0"], m, fr["sid"], fr["cls"],
                                icraft_run, model_json, model_raw, no_infer)
            agg[m]["n"] += 1
            agg[m]["gate_pass"] += out["gated"]
            if out["gated"]:
                agg[m]["gated_correct"] += out["correct"]
            agg[m]["e2e_correct"] += out["correct"]
            est = out["est"]
            rec = out["rec"]
            comp_rows.append([
                m, fr["sid"], fr["cls"], c.LABELS[fr["cls"]],
                str(est["timing_offset"]), "%.2f" % est["coarse_cfo_hz"],
                "%.3f" % est["fractional_timing"],
                "%.6f" % abs(est["a"]), "%.6f" % abs(est["b"]),
                "%.6f" % est["training_residual_rel"], out["gated"], out["pred"],
                out["correct"], "%.4f" % rec.mean().real, "%.4f" % rec.mean().imag,
            ])

    prefix = "reestimate_%s" % name
    c.write_tsv(out_dir / (prefix + "_comparison.tsv"), comp_header, comp_rows)

    # Condition-number / post-eq metrics on the BASELINE (M0) a/b of every frame.
    cond_header = ["source_index", "class_name", "a_mag", "b_mag", "ratio_b_over_a",
                   "cond_2x2", "denom", "inverse_gain_1_over_a",
                   "post_eq_signal_rms", "post_eq_noise_rms", "post_eq_snr_db",
                   "recovered_dc_re", "recovered_dc_im", "recovered_dc_mag",
                   "dc_over_signal", "recovered_signal_rms"]
    cond_rows = []
    for fr in frames:
        est0 = fr["est0"]
        rec0 = R.recover_v2(fr["raw"], est0)
        cond_rows.append(condition_row(fr["r"], est0, rec0))
    c.write_tsv(out_dir / (prefix + "_condition_metrics.tsv"), cond_header, cond_rows)

    summary = {}
    for m in MODELS:
        a = agg[m]
        summary[m] = {
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
    args = ap.parse_args(argv)

    capture_dir = Path(args.capture_dir)
    old_capture_dir = Path(args.old_capture_dir)
    model_dir = Path(args.model_dir)
    icraft_run = Path(args.icraft_run)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mf = args.max_frames if args.max_frames > 0 else 24

    # fix2 target (latest RF session): strict 23-col schema.
    target_results = c.load_results_tsv(capture_dir / "board_independent_rx_results.tsv")
    # old RF session (v1/v2 delivery): 19-col schema; read leniently.
    _, old_rows = c.read_tsv(old_capture_dir / "board_independent_rx_results.tsv")
    old_results = [{"source_index": int(r["source_index"]),
                    "class_index": int(r["class_index"])} for r in old_rows]

    summaries = {}
    summaries["rf_fix2_target"] = process_session(
        "fix2_target", capture_dir, target_results, model_dir, icraft_run,
        out_dir, args.no_infer, mf)
    summaries["old_rf_session"] = process_session(
        "old_rf_v1v2", old_capture_dir, old_results, model_dir, icraft_run,
        out_dir, args.no_infer, mf)

    c.dumps_json(summaries, out_dir / "reestimate_summary.json")

    for sess, sm in summaries.items():
        print("[reestimate] %s:" % sess)
        for m in MODELS:
            a = sm[m]
            print("  %-22s gate=%2d/24  gated_acc=%s  e2e=%2d/24 (%.4f)" % (
                m, a["gate_pass"],
                ("%.4f" % a["gated_accuracy"]) if a["gated_accuracy"] is not None
                else "n/a",
                a["end_to_end_correct"], a["end_to_end_accuracy"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
