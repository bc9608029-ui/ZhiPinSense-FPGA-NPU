#!/usr/bin/env python3
"""analyze_fix3_layers.py -- Fix3 Phase B: layered difference localization.

Localizes, per frame, where the recovered-vs-clean degradation enters the
recovery chain.  For each of the 24 frames it measures, at each stage:

  * RX (aligned, int16 counts)   settling / guard / payload segment DC + RMS,
    and the payload-DC linear drift slope (diagnostic only).
  * de-rotated payload           segment DC + RMS.
  * wide-linear-inverse output   segment DC + RMS (before unscale).
  * recovered model-input tensor DC / RMS vs the clean TX tensor.

And, against the clean reference tensor (the manifest model_input for the same
waveform), the complex correlation, best complex gain, residual-after-gain, and
residual-after-gain+DC.  The recovered-vs-clean comparison is diagnostic only;
it uses the clean tensor (a TX-side reference) and is NEVER fed back into any
candidate recovery fix (red line: no per-sample DC/scale selection).

Outputs (--out-dir):
  per_sample_layer_metrics.tsv

Usage:
    python -I scripts/analyze_fix3_layers.py \
        --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244 \
        --clean-dir  F:/嵌赛/fix10class24_waveform_correct_v2_work/replay_out/layers \
        --out-dir results
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fix3_common as c
import fix3_recovery as R


def seg_mean(x: np.ndarray, start: int, end: int) -> complex:
    s = x[start:end]
    return complex(s.mean())


def seg_rms(x: np.ndarray, start: int, end: int) -> float:
    s = x[start:end]
    return float(np.sqrt(np.mean(np.abs(s - s.mean()) ** 2)))


def drift_slope(x: np.ndarray, start: int, end: int) -> complex:
    """Least-squares linear slope of the segment DC (per 1024-sample block)."""
    s = x[start:end]
    nseg = len(s) // 1024
    means = np.array([s[k * 1024:(k + 1) * 1024].mean() for k in range(nseg)])
    t = np.arange(nseg, dtype=np.float64) - (nseg - 1) / 2.0
    slope = np.sum(t * (means - means.mean())) / np.sum(t * t)
    return complex(slope)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture-dir", required=True)
    ap.add_argument("--clean-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    capture_dir = Path(args.capture_dir)
    clean_dir = Path(args.clean_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = c.load_results_tsv(capture_dir / "board_independent_rx_results.tsv")

    header = [
        "source_index", "class_index", "class_name",
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
        "training_residual_rel", "gated", "board_pred",
    ]
    rows = []

    for r in results:
        sid = int(r["source_index"])
        cls = int(r["class_index"])
        rx_burst, off = R.load_burst(capture_dir, sid)
        est = R.estimate_public_reference_fix2(rx_burst)
        aligned = R.aligned_burst(rx_burst, est)

        settle_dc = seg_mean(aligned, R.SETTLE_START, R.SETTLE_END)
        guard_dc = seg_mean(aligned, R.GUARD_START, R.GUARD_END)
        payload_dc = seg_mean(aligned, R.PAYLOAD_START, R.PAYLOAD_END)
        slope = drift_slope(aligned, R.PAYLOAD_START, R.PAYLOAD_END)

        derot_b = R.derot(aligned, est["coarse_cfo_hz"])
        derot_payload_dc = seg_mean(derot_b, R.PAYLOAD_START, R.PAYLOAD_END)

        payload = derot_b[R.PAYLOAD_START:R.PAYLOAD_END]
        wl = R.wide_linear_inverse(payload, est["a"], est["b"])
        shifted = R.frac_delay_sinc(wl, -est["fractional_timing"])
        rec = shifted[:R.MODEL_WINDOW] * R.V2_UNSCALE

        clean = R.load_tensor(clean_dir / ("%d.orig.tensor.bin" % sid))

        # correlation + best gain + residuals (diagnostic, clean is TX-side)
        rec0 = rec - rec.mean()
        clean0 = clean - clean.mean()
        den = np.linalg.norm(rec0) * np.linalg.norm(clean0)
        corr = float(abs(np.vdot(rec0, clean0)) / den) if den > 0 else float("nan")
        g = np.vdot(clean0, rec0) / np.vdot(clean0, clean0) if np.vdot(clean0, clean0) != 0 else 0.0
        resid_gain = float(np.linalg.norm(rec0 - g * clean0) / np.linalg.norm(rec0))
        d_off = rec.mean() - g * clean.mean()
        resid_gain_dc = float(np.linalg.norm(rec - g * clean - d_off) / np.linalg.norm(rec))

        rows.append([
            sid, cls, r["class_name"],
            "%.4f" % settle_dc.real, "%.4f" % settle_dc.imag,
            "%.4f" % seg_rms(aligned, R.SETTLE_START, R.SETTLE_END),
            "%.4f" % guard_dc.real, "%.4f" % guard_dc.imag,
            "%.4f" % seg_rms(aligned, R.GUARD_START, R.GUARD_END),
            "%.4f" % payload_dc.real, "%.4f" % payload_dc.imag,
            "%.4f" % seg_rms(aligned, R.PAYLOAD_START, R.PAYLOAD_END),
            "%.4f" % slope.real, "%.4f" % slope.imag,
            "%.4f" % derot_payload_dc.real, "%.4f" % derot_payload_dc.imag,
            "%.4f" % wl[:R.MODEL_WINDOW].mean().real, "%.4f" % wl[:R.MODEL_WINDOW].mean().imag,
            "%.4f" % float(np.sqrt(np.mean(np.abs(wl[:R.MODEL_WINDOW]) ** 2))),
            "%.4f" % rec.mean().real, "%.4f" % rec.mean().imag,
            "%.4f" % float(np.sqrt(np.mean(np.abs(rec) ** 2))),
            "%.4f" % clean.mean().real, "%.4f" % clean.mean().imag,
            "%.4f" % float(np.sqrt(np.mean(np.abs(clean) ** 2))),
            "%.4f" % corr, "%.4f" % g.real, "%.4f" % g.imag,
            "%.4f" % resid_gain, "%.4f" % resid_gain_dc,
            "%.6f" % (abs(est["a"]) ** 2 - abs(est["b"]) ** 2),
            "%.4f" % abs(est["a"]), "%.4f" % abs(est["b"]),
            "%.4f" % float(est["training_residual_rel"]),
            int(r["gated"]), int(r["board_pred"]),
        ])

    c.write_tsv(out_dir / "per_sample_layer_metrics.tsv", header, rows)
    print("[layers] wrote per_sample_layer_metrics.tsv (%d rows)" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
