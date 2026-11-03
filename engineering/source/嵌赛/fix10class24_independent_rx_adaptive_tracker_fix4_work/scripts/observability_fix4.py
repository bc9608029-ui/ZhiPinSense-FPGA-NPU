#!/usr/bin/env python3
"""observability_fix4.py -- Phase 1: can the 4 public DC observations see the
payload-interior drift?

Pure offline.  For every frame of the two real dual-SDR captures it computes the
4 public DC observations (settle/train/guard/tail block means) and asks the
Fix4-S9(1) question: is the payload drift OBSERVABLE from these 4 sparse anchors,
or is it structurally unobservable (which would cap every tracker at Fix3's
2/24 regardless of model)?

Outputs:
    observability_<session>_observations.tsv   per-frame 4-obs + slope/scatter
    observability_summary.json                  aggregate non-monotonic / scatter
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fix4_common as c
import fix3_recovery as R


def frame_obs(raw: np.ndarray, est0: dict) -> dict:
    aligned = R.aligned_burst(raw, est0)
    obs = c.public_dc_observations(aligned)
    ts = np.array([o[0] for o in obs], dtype=np.float64)
    zs = np.array([o[1] for o in obs], dtype=np.complex128)
    # early slope (settle->train), late slope (guard->tail)
    early = (zs[1] - zs[0]) / (ts[1] - ts[0])
    late = (zs[3] - zs[2]) / (ts[3] - ts[2])
    # LS line through the 4 obs (the constant-velocity / T4 model); scatter = fit residual
    A = np.column_stack([np.ones(4), ts])
    coef_re, *_ = np.linalg.lstsq(A, zs.real, rcond=None)
    coef_im, *_ = np.linalg.lstsq(A, zs.imag, rcond=None)
    line = (coef_re[0] + coef_re[1] * ts) + 1j * (coef_im[0] + coef_im[1] * ts)
    resid = float(np.max(np.abs(zs - line)))
    # non-monotonic: imag (or real) is not monotone across settle/train/guard/tail
    def nonmono(v):
        d = np.diff(v)
        return bool(np.any(d > 0) and np.any(d < 0))
    return {"ts": ts, "zs": zs, "early": early, "late": late,
            "line_slope": complex(coef_re[1], coef_im[1]),
            "scatter": resid,
            "nonmono_re": nonmono(zs.real), "nonmono_im": nonmono(zs.imag),
            "drift_span": float(np.max(np.abs(zs - zs[0])))}


def process(sess_name, capture_dir: Path, results, out_dir: Path) -> dict:
    header = ["source_index", "class_index",
              "settle_re", "settle_im", "train_re", "train_im",
              "guard_re", "guard_im", "tail_re", "tail_im",
              "early_slope_re", "early_slope_im", "late_slope_re", "late_slope_im",
              "line_slope_re", "line_slope_im", "scatter", "drift_span",
              "nonmono_re", "nonmono_im"]
    rows = []
    agg = {"n": 0, "nonmono_re": 0, "nonmono_im": 0,
           "scatter": [], "drift_span": [], "late_slope_mag": []}
    for r in results:
        sid = int(r["source_index"]); cls = int(r["class_index"])
        raw, _ = R.load_burst(capture_dir, sid)
        est0 = R.estimate_public_reference_fix2(raw)
        o = frame_obs(raw, est0)
        z = o["zs"]
        rows.append([sid, cls,
                     "%.5f" % z[0].real, "%.5f" % z[0].imag,
                     "%.5f" % z[1].real, "%.5f" % z[1].imag,
                     "%.5f" % z[2].real, "%.5f" % z[2].imag,
                     "%.5f" % z[3].real, "%.5f" % z[3].imag,
                     "%.6f" % o["early"].real, "%.6f" % o["early"].imag,
                     "%.6f" % o["late"].real, "%.6f" % o["late"].imag,
                     "%.6f" % o["line_slope"].real, "%.6f" % o["line_slope"].imag,
                     "%.5f" % o["scatter"], "%.5f" % o["drift_span"],
                     int(o["nonmono_re"]), int(o["nonmono_im"])])
        agg["n"] += 1
        agg["nonmono_re"] += int(o["nonmono_re"])
        agg["nonmono_im"] += int(o["nonmono_im"])
        agg["scatter"].append(o["scatter"])
        agg["drift_span"].append(o["drift_span"])
        agg["late_slope_mag"].append(abs(o["late"]))
    c.FC.write_tsv(out_dir / ("observability_%s_observations.tsv" % sess_name),
                   header, rows)
    return {"n": agg["n"], "nonmono_re": agg["nonmono_re"],
            "nonmono_im": agg["nonmono_im"],
            "scatter_median": float(np.median(agg["scatter"])),
            "scatter_max": float(np.max(agg["scatter"])),
            "drift_span_median": float(np.median(agg["drift_span"])),
            "drift_span_max": float(np.max(agg["drift_span"])),
            "late_slope_mag_median": float(np.median(agg["late_slope_mag"]))}


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--capture-dir", required=True)
    ap.add_argument("--old-capture-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    cap = Path(args.capture_dir); old = Path(args.old_capture_dir)
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)

    tgt = c.FC.load_results_tsv(cap / "board_independent_rx_results.tsv")
    _, old_rows = c.FC.read_tsv(old / "board_independent_rx_results.tsv")
    old_res = [{"source_index": int(r["source_index"]),
                "class_index": int(r["class_index"])} for r in old_rows]

    summ = {}
    summ["rf_fix2_target"] = process("fix2_target", cap, tgt, out)
    summ["old_rf_session"] = process("old_rf_v1v2", old, old_res, out)
    c.FC.dumps_json(summ, out / "observability_summary.json")
    for k, v in summ.items():
        print("[observability] %-16s n=%d nonmono(im)=%d/%d  scatter med=%.3f max=%.3f"
              "  drift_span med=%.3f max=%.3f" % (
                  k, v["n"], v["nonmono_im"], v["n"],
                  v["scatter_median"], v["scatter_max"],
                  v["drift_span_median"], v["drift_span_max"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
