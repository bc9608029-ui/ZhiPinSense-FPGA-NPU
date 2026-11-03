#!/usr/bin/env python3
"""digital_counterexample_r1.py -- real digital counterexample (REVIEW-R1 req 7).

Reads the 24 REAL v2 tx_package/<sid>.burst.i16 (the frozen, corrected waveforms,
NOT synthetic random public blocks).  With NO RF, verifies:

  (a) the CORRECTED reference-subtracted public residual is ~ quantization error
      (residual anchor magnitude << signal amplitude and << the reference's own
      non-zero mean), proving the corrected definition no longer leaks the known
      sequence mean into the "DC" estimate;
  (b) actually runs the frozen BF16 24-frame classification (T0 baseline);
  (c) MEASURES digital_no_new_flips -- runs every DC tracker (C1,T1..T6) and
      compares each frame's prediction to T0, instead of hardcoding true.

Requirements: read real bursts, no synthetic random public blocks, actually run
BF16 classification, no hardcoded digital_no_new_flips=true.

Usage:
    python -I scripts/digital_counterexample_r1.py \
        --tx-dir F:/嵌赛/fix10class24_waveform_correct_v2_work/tx_package \
        --model-dir F:/嵌赛/.../model_rml24_bf16 \
        --icraft-run D:/icraft/bin/icraft-run.exe \
        --out-dir results_r1 \
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
import fix4_residual_ref as RREF
import trackers_fix4_r1 as TK

TRACKER_LIST = ["T0_baseline", "C1_settle_dc_constant",
                "T1_blockwise_linear", "T2_exp_transient", "T3_hermite",
                "T4_kalman", "T5_kalman_crossframe", "T6_best_alternate"]


def load_manifest(tx_dir: Path) -> dict[int, int]:
    """sid -> class_index from the frozen v2 manifest (fail-closed)."""
    _, rows = c.FC.read_tsv(tx_dir / "public_protocol_tx_manifest.tsv")
    m = {}
    for r in rows:
        sid = int(r["source_index"])
        cls = int(r["class_index"])
        if sid in m:
            c.FC.fail("duplicate source_index=%d in manifest" % sid)
        m[sid] = cls
    if set(m) != set(range(1, 25)):
        c.FC.fail("manifest source_index set != 1..24")
    return m


def run_frame(sid: int, cls: int, rx: np.ndarray, est0: dict,
              icraft_run, model_json, model_raw, no_infer: bool) -> dict:
    timing0 = int(est0["timing_offset"])

    # residual anchor magnitude (corrected definition) -> quantization floor check
    mags = RREF.residual_anchor_magnitudes(rx, est0, sub_len=RREF.SUB_LEN)
    max_anchor = float(mags.max())

    out = {"sid": sid, "cls": cls, "max_anchor": max_anchor, "pred": {}}

    # T0 baseline
    rec0 = R.recover_v2(rx, est0)
    pred0 = -1
    if not no_infer:
        pred0 = int(np.argmax(R.run_host_infer(icraft_run, model_json, model_raw, rec0)))
    out["pred"]["T0_baseline"] = pred0
    out["gated_T0"] = int(est0["training_residual_rel"] <= c.GATE)

    # trackers (C1 + T1..T6): subtract DC from residual anchors, re-estimate, infer.
    for t in TRACKER_LIST[1:]:
        if t == "T6_best_alternate":
            aligned = R.aligned_burst(rx, est0)
            best = None
            for s in TK.SELECTABLE[:4]:   # T1..T4 (T5 excluded, intra-frame)
                dc_al, _ = TK.dc_trajectory(s, aligned, est0, None)
                dc_raw = np.roll(dc_al, timing0) if timing0 else dc_al
                est = R.estimate_public_reference_fix2(rx - dc_raw)
                rr = est["training_residual_rel"]
                if best is None or rr < best[0]:
                    best = (rr, dc_raw, est)
            _, dc_raw, est2 = best
            rec = R.recover_v2(rx - dc_raw, est2)
        else:
            aligned = R.aligned_burst(rx, est0)
            dc_al, _ = TK.dc_trajectory(t, aligned, est0, None)
            dc_raw = np.roll(dc_al, timing0) if timing0 else dc_al
            est2 = R.estimate_public_reference_fix2(rx - dc_raw)
            rec = R.recover_v2(rx - dc_raw, est2)
        pred = -1
        if not no_infer:
            pred = int(np.argmax(R.run_host_infer(icraft_run, model_json, model_raw, rec)))
        out["pred"][t] = pred
        out["gated_" + t] = int(est2["training_residual_rel"] <= c.GATE)
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tx-dir", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--icraft-run", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--no-infer", action="store_true")
    ap.add_argument("--max-frames", type=int, default=0)
    args = ap.parse_args(argv)

    tx_dir = Path(args.tx_dir)
    model_dir = Path(args.model_dir)
    icraft_run = Path(args.icraft_run)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mf = args.max_frames if args.max_frames > 0 else 24

    model_json = model_dir / "rml24_adamrv11_bf16.json"
    model_raw = model_dir / "rml24_adamrv11_bf16.raw"
    if c.FC.sha256_file(model_json) != c.FROZEN_MODEL_JSON_SHA256:
        c.FC.fail("model json SHA mismatch")
    if c.FC.sha256_file(model_raw) != c.FROZEN_MODEL_RAW_SHA256:
        c.FC.fail("model raw SHA mismatch")

    sid2cls = load_manifest(tx_dir)
    sids = sorted(sid2cls)[:mf]

    header = ["sid", "class_index", "class_name", "max_residual_anchor",
              "residual_vs_reference_mean_frac"] + \
             ["pred_" + t for t in TRACKER_LIST]
    rows = []
    for sid in sids:
        cls = sid2cls[sid]
        inter = np.frombuffer((tx_dir / ("%d.burst.i16" % sid)).read_bytes(),
                              dtype="<i2")
        rx = _deinterleave(inter)
        est0 = R.estimate_public_reference_fix2(rx)
        o = run_frame(sid, cls, rx, est0, icraft_run, model_json, model_raw,
                      args.no_infer)
        ref_mean_mag = abs(RREF.reference_mean("train"))
        frac = o["max_anchor"] / ref_mean_mag if ref_mean_mag > 0 else float("inf")
        row = [sid, cls, c.FC.LABELS[cls], "%.4f" % o["max_anchor"], "%.4f" % frac]
        row += [str(o["pred"][t]) for t in TRACKER_LIST]
        rows.append(row)
        print("sid=%02d %-9s max_resid_anchor=%.4f (ref_mean=%.1f, frac=%.4f)" %
              (sid, c.FC.LABELS[cls], o["max_anchor"], ref_mean_mag, frac))

    c.FC.write_tsv(out_dir / "digital_counterexample_r1.tsv", header, rows)

    # measured digital baseline + no-new-flips (vs T0)
    base_correct = sum(1 for r in rows if int(r[header.index("pred_T0_baseline")]) ==
                       int(r[header.index("class_index")]))
    flip_count = {t: 0 for t in TRACKER_LIST[1:]}
    for r in rows:
        t0 = int(r[header.index("pred_T0_baseline")])
        for t in TRACKER_LIST[1:]:
            if int(r[header.index("pred_" + t)]) != t0:
                flip_count[t] += 1

    summary = {
        "token": "M29-RML24-FIX10CLASS24-INDEPENDENT-RX-ADAPTIVE-TRACKER-FIX4-REVIEW-R1-DIGITAL",
        "n_frames": len(rows),
        "digital_baseline_correct": base_correct,
        "digital_baseline_n": len(rows),
        "max_residual_anchor_over_frames": float(max(
            float(r[header.index("max_residual_anchor")]) for r in rows)),
        "train_reference_mean_mag": abs(RREF.reference_mean("train")),
        "tail_reference_mean_mag": abs(RREF.reference_mean("tail")),
        "digital_no_new_flips": {t: (flip_count[t] == 0) for t in flip_count},
        "new_flips_per_tracker": flip_count,
    }
    c.FC.dumps_json(summary, out_dir / "digital_counterexample_r1_summary.json")
    print("\ndigital baseline = %d/%d correct" % (base_correct, len(rows)))
    print("measured new flips vs T0 per tracker: %s" % flip_count)
    print("digital_no_new_flips (measured): %s" % summary["digital_no_new_flips"])
    return 0


def _deinterleave(inter: np.ndarray) -> np.ndarray:
    return inter[0::2].astype(np.float64) + 1j * inter[1::2].astype(np.float64)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
