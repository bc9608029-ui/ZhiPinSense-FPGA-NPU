#!/usr/bin/env python3
"""observability_fix4_r1.py -- corrected observability on residual anchors (REVIEW-R1).

Phase 1 of REVIEW-R1: can the CORRECTED residual anchors (per-sample reference
subtraction, then sub-block means) see the payload-interior DC drift, or is it
structurally unobservable (which would cap every tracker regardless of model)?

Two questions are answered:

  A. WITHIN-FRAME: 20 residual anchors (settle 4 / train 4 / guard 8 / tail 4)
     -> scatter around the constant-velocity LS line, real/imag non-monotonicity,
        drift_span (max |anchor_i - anchor_0|).  A large scatter relative to the
        anchor magnitude means the payload-interior trajectory is NOT recoverable
        from the public references (requirement 10's mathematical statement).

  B. CROSS-FRAME (requirement 9): the residual-anchor correlation between
     CONSECUTIVE frames, computed directly in REAL acquisition time order
     (source_index 1..24 = the sequential capture order).  The T5 cross-frame
     prior is justified only if this measured correlation is significant; if it
     is not, the old "帧间不相关" claim is now a MEASUREMENT, not an assumption.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fix4_common as c
import fix3_recovery as R
import fix4_residual_ref as RREF


def frame_obs(raw: np.ndarray, est0: dict) -> dict:
    aligned = R.aligned_burst(raw, est0)
    obs = RREF.residual_anchors(aligned, est0, sub_len=RREF.SUB_LEN)
    ts = np.array([o[0] for o in obs], dtype=np.float64)
    zs = np.array([o[1] for o in obs], dtype=np.complex128)

    # constant-velocity LS line through ALL anchors (the T4 model); scatter = max
    # residual of anchors around that line.
    A = np.column_stack([np.ones(len(ts)), ts])
    coef_re, *_ = np.linalg.lstsq(A, zs.real, rcond=None)
    coef_im, *_ = np.linalg.lstsq(A, zs.imag, rcond=None)
    line = (coef_re[0] + coef_re[1] * ts) + 1j * (coef_im[0] + coef_im[1] * ts)
    scatter = float(np.max(np.abs(zs - line)))

    def nonmono(v):
        d = np.diff(v)
        return bool(np.any(d > 0) and np.any(d < 0))

    anchor_mag = float(np.mean(np.abs(zs)))
    return {"ts": ts, "zs": zs,
            "line_slope": complex(coef_re[1], coef_im[1]),
            "scatter": scatter,
            "scatter_over_mag": (scatter / anchor_mag) if anchor_mag > 0 else float("inf"),
            "anchor_mag": anchor_mag,
            "nonmono_re": nonmono(zs.real), "nonmono_im": nonmono(zs.imag),
            "drift_span": float(np.max(np.abs(zs - zs[0])))}


def complex_corr(x: np.ndarray, y: np.ndarray) -> float:
    """Normalized |complex Pearson correlation| in [0,1]."""
    x = x - np.mean(x)
    y = y - np.mean(y)
    sx = float(np.sqrt(np.sum(np.abs(x) ** 2)))
    sy = float(np.sqrt(np.sum(np.abs(y) ** 2)))
    if sx == 0.0 or sy == 0.0:
        return 0.0
    return float(abs(np.vdot(x, y)) / (sx * sy))


def process(sess_name, capture_dir: Path, results, out_dir: Path) -> dict:
    header = ["source_index", "class_index",
              "settle_re", "settle_im", "train_re", "train_im",
              "guard_re", "guard_im", "tail_re", "tail_im",
              "line_slope_re", "line_slope_im", "scatter", "scatter_over_mag",
              "anchor_mag", "drift_span", "nonmono_re", "nonmono_im"]
    rows = []
    # per-frame anchor snapshots for cross-frame correlation (time order)
    anchor_by_sid = {}   # sid -> (tail_anchor, settle_anchor)
    agg = {"n": 0, "nonmono_re": 0, "nonmono_im": 0,
           "scatter": [], "scatter_over_mag": [], "drift_span": []}

    # results are in source_index order 1..24 == real acquisition order.
    for r in results:
        sid = int(r["source_index"])
        cls = int(r["class_index"])
        raw, _ = R.load_burst(capture_dir, sid)
        est0 = R.estimate_public_reference_fix2(raw)
        o = frame_obs(raw, est0)
        z = o["zs"]
        # block-mean summaries at the 4 block centers (for continuity with R1's
        # table), still derived from residual anchors via interpolation-free means:
        # settle = mean of its 4 sub-block anchors, etc.
        n_settle = RREF.BLOCK_LEN["settle"] // RREF.SUB_LEN      # 4
        n_train = RREF.BLOCK_LEN["train"] // RREF.SUB_LEN        # 4
        n_guard = RREF.BLOCK_LEN["guard"] // RREF.SUB_LEN        # 8
        settle_z = np.mean(z[0:n_settle])
        train_z = np.mean(z[n_settle:n_settle + n_train])
        guard_z = np.mean(z[n_settle + n_train:n_settle + n_train + n_guard])
        tail_z = np.mean(z[n_settle + n_train + n_guard:])
        rows.append([sid, cls,
                     "%.5f" % settle_z.real, "%.5f" % settle_z.imag,
                     "%.5f" % train_z.real, "%.5f" % train_z.imag,
                     "%.5f" % guard_z.real, "%.5f" % guard_z.imag,
                     "%.5f" % tail_z.real, "%.5f" % tail_z.imag,
                     "%.6f" % o["line_slope"].real, "%.6f" % o["line_slope"].imag,
                     "%.5f" % o["scatter"], "%.5f" % o["scatter_over_mag"],
                     "%.5f" % o["anchor_mag"], "%.5f" % o["drift_span"],
                     int(o["nonmono_re"]), int(o["nonmono_im"])])
        agg["n"] += 1
        agg["nonmono_re"] += int(o["nonmono_re"])
        agg["nonmono_im"] += int(o["nonmono_im"])
        agg["scatter"].append(o["scatter"])
        agg["scatter_over_mag"].append(o["scatter_over_mag"])
        agg["drift_span"].append(o["drift_span"])
        anchor_by_sid[sid] = (tail_z, settle_z)

    c.FC.write_tsv(out_dir / ("observability_%s_observations.tsv" % sess_name),
                   header, rows)

    # cross-frame correlation in real acquisition time order (sid 1..23 -> 2..24)
    sids = sorted(anchor_by_sid)
    tail_seq = np.array([anchor_by_sid[s][0] for s in sids[:-1]])
    settle_seq = np.array([anchor_by_sid[s][1] for s in sids[1:]])
    xf_corr = complex_corr(tail_seq, settle_seq) if len(sids) >= 2 else 0.0

    return {"n": agg["n"], "nonmono_re": agg["nonmono_re"],
            "nonmono_im": agg["nonmono_im"],
            "scatter_median": float(np.median(agg["scatter"])),
            "scatter_max": float(np.max(agg["scatter"])),
            "scatter_over_mag_median": float(np.median(agg["scatter_over_mag"])),
            "drift_span_median": float(np.median(agg["drift_span"])),
            "drift_span_max": float(np.max(agg["drift_span"])),
            "cross_frame_tail_settle_corr": float(xf_corr)}


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture-dir", required=True)
    ap.add_argument("--old-capture-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    cap = Path(args.capture_dir)
    old = Path(args.old_capture_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    tgt = c.FC.load_results_tsv(cap / "board_independent_rx_results.tsv")
    _, old_rows = c.FC.read_tsv(old / "board_independent_rx_results.tsv")
    old_res = [{"source_index": int(r["source_index"]),
                "class_index": int(r["class_index"])} for r in old_rows]

    summ = {}
    summ["rf_fix2_target"] = process("fix2_target", cap, tgt, out)
    summ["old_rf_session"] = process("old_rf_v1v2", old, old_res, out)
    c.FC.dumps_json(summ, out / "observability_fix4_r1_summary.json")
    for k, v in summ.items():
        print("[observability_r1] %-16s n=%d nonmono(im)=%d/%d  scatter med=%.3f "
              "scatter/mag med=%.3f  drift_span med=%.3f  crossframe_corr=%.3f" % (
                  k, v["n"], v["nonmono_im"], v["n"],
                  v["scatter_median"], v["scatter_over_mag_median"],
                  v["drift_span_median"], v["cross_frame_tail_settle_corr"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
