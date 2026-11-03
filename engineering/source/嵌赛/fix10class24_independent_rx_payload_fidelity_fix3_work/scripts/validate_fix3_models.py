#!/usr/bin/env python3
"""validate_fix3_models.py -- Fix3 Phase C: validate candidate recovery fixes.

Tests, against the byte-exact host reconstruction of the board fix2 recovery,
the candidate offset / LO-leak models (all category-independent, payload-free):

  M0 baseline        fix2 recovery, unchanged.
  M1 settle-DC       subtract settling-zero [1024:2048] mean (pre de-rotation).
  M2 guard-DC        subtract guard-zero [56832:58880] mean.
  M3 settle+guard    subtract the average of the two silence-region means.
  M4 linear-DC       subtract a linear ramp fit to the two silence means,
                     evaluated at the payload start.
  M5 oracle-DC       subtract the actual payload mean (DIAGNOSTIC UPPER BOUND
                     ONLY -- forbidden in production: it reads payload IQ).

Each model is re-classified with the frozen BF16 model on the Host backend and
scored with the intact 24-frame denominator (gate rejects are never dropped).
M1-M4 never read payload IQ / labels / source ID; M5 is explicitly labelled a
forbidden oracle bound.

Also emits: heldout_validation.tsv (estimate-on-silence / validate-on-payload),
cross_session_validation.tsv (digital file loopback vs RF dual capture),
synthetic_counterexamples.tsv (injected DC -> wide-linear amplification), and
timing_breakdown.tsv (host stage timings).

Usage:
    python -I scripts/validate_fix3_models.py \
        --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244 \
        --file-capture-dir F:/嵌赛/board_capture/rml24_fix2_v2_file_1773373830_244 \
        --model-dir F:/嵌赛/.../model_rml24_bf16 \
        --icraft-run D:/icraft/bin/icraft-run.exe \
        --out-dir results \
        [--no-infer]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fix3_common as c
import fix3_recovery as R

MODELS = ["M0_baseline", "M1_settle_dc", "M2_guard_dc",
          "M3_settle_guard_avg", "M4_linear_dc", "M5_oracle_dc"]


def model_dc(model: str, aligned: np.ndarray) -> complex:
    if model == "M0_baseline":
        return 0.0 + 0j
    if model == "M1_settle_dc":
        return complex(aligned[R.SETTLE_START:R.SETTLE_END].mean())
    if model == "M2_guard_dc":
        return complex(aligned[R.GUARD_START:R.GUARD_END].mean())
    if model == "M3_settle_guard_avg":
        s = aligned[R.SETTLE_START:R.SETTLE_END].mean()
        g = aligned[R.GUARD_START:R.GUARD_END].mean()
        return complex((s + g) / 2.0)
    if model == "M4_linear_dc":
        s = aligned[R.SETTLE_START:R.SETTLE_END].mean()
        g = aligned[R.GUARD_START:R.GUARD_END].mean()
        t_s = (R.SETTLE_START + R.SETTLE_END) / 2.0
        t_g = (R.GUARD_START + R.GUARD_END) / 2.0
        t_p = (R.PAYLOAD_START + R.PAYLOAD_END) / 2.0
        frac = (t_p - t_s) / (t_g - t_s)
        return complex(s + (g - s) * frac)
    if model == "M5_oracle_dc":
        return complex(aligned[R.PAYLOAD_START:R.PAYLOAD_END].mean())
    raise ValueError(model)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture-dir", required=True)
    ap.add_argument("--file-capture-dir", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--icraft-run", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--no-infer", action="store_true")
    args = ap.parse_args(argv)

    capture_dir = Path(args.capture_dir)
    file_capture_dir = Path(args.file_capture_dir)
    model_dir = Path(args.model_dir)
    icraft_run = Path(args.icraft_run)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_json = model_dir / "rml24_adamrv11_bf16.json"
    model_raw = model_dir / "rml24_adamrv11_bf16.raw"
    if c.sha256_file(model_json) != c.FROZEN_MODEL_JSON_SHA256:
        c.fail("model json SHA mismatch")
    if c.sha256_file(model_raw) != c.FROZEN_MODEL_RAW_SHA256:
        c.fail("model raw SHA mismatch")

    results = c.load_results_tsv(capture_dir / "board_independent_rx_results.tsv")

    # ---- precompute estimates + tensors (shared across models) ----
    frames = []
    for r in results:
        sid = int(r["source_index"])
        rx_burst, off = R.load_burst(capture_dir, sid)
        est = R.estimate_public_reference_fix2(rx_burst)
        aligned = R.aligned_burst(rx_burst, est)
        frames.append({"sid": sid, "cls": int(r["class_index"]),
                       "rx_burst": rx_burst, "est": est, "aligned": aligned,
                       "board_pred": int(r["board_pred"]),
                       "gated": int(r["gated"])})

    # ---- offset model comparison ----
    comp_header = ["model", "source_index", "class_index", "class_name",
                   "recovered_dc_re", "recovered_dc_im", "pred", "correct",
                   "training_residual_rel", "gated"]
    comp_rows = []
    agg = {m: {"correct": 0, "classified": 0, "n": 0} for m in MODELS}

    for m in MODELS:
        for fr in frames:
            dc = model_dc(m, fr["aligned"])
            if m == "M0_baseline":
                rec = R.recover_v2(fr["rx_burst"], fr["est"])
            else:
                rec = R.recover_v2_with_dc(fr["rx_burst"], fr["est"], dc)
            pred = -1
            if fr["gated"] and not args.no_infer:
                pred = int(np.argmax(R.run_host_infer(
                    icraft_run, model_json, model_raw, rec)))
            elif fr["gated"] and args.no_infer:
                pred = fr["board_pred"]  # dry-run placeholder
            correct = 1 if pred == fr["cls"] else 0
            agg[m]["n"] += 1
            if pred >= 0:
                agg[m]["classified"] += 1
                agg[m]["correct"] += correct
            comp_rows.append([
                m, fr["sid"], fr["cls"], c.LABELS[fr["cls"]],
                "%.4f" % rec.mean().real, "%.4f" % rec.mean().imag,
                pred, correct,
                "%.4f" % float(fr["est"]["training_residual_rel"]),
                fr["gated"],
            ])
    c.write_tsv(out_dir / "offset_model_comparison.tsv", comp_header, comp_rows)

    # ---- heldout validation (estimate on silence, validate on payload) ----
    held_header = ["model", "dc_source", "n", "gated", "classified", "correct",
                   "end_to_end_accuracy", "mean_recovered_dc_im"]
    held_rows = []
    for m, src in [("M0_baseline", "none"), ("M1_settle_dc", "settle"),
                   ("M2_guard_dc", "guard"), ("M3_settle_guard_avg", "settle+guard"),
                   ("M4_linear_dc", "linear"), ("M5_oracle_dc", "payload(oracle)")]:
        a = agg[m]
        dcims = [float(R.recover_v2_with_dc(fr["rx_burst"], fr["est"],
                                            model_dc(m, fr["aligned"])).mean().imag)
                 if m != "M0_baseline"
                 else float(R.recover_v2(fr["rx_burst"], fr["est"]).mean().imag)
                 for fr in frames]
        held_rows.append([m, src, a["n"], sum(1 for f in frames if f["gated"]),
                          a["classified"], a["correct"],
                          "%.4f" % (a["correct"] / a["n"] if a["n"] else 0.0),
                          "%.4f" % (sum(dcims) / len(dcims) if dcims else float("nan"))])
    c.write_tsv(out_dir / "heldout_validation.tsv", held_header, held_rows)

    # ---- cross-session validation (digital file loopback vs RF dual) ----
    x_header = ["session", "a_mag", "b_mag", "wl_denom", "cfo_min", "cfo_max",
                "correct", "gated", "classified", "end_to_end_accuracy"]
    x_rows = []

    def session_row(session, cap, use_est=True):
        res = c.load_results_tsv(cap / "board_independent_rx_results.tsv")
        a_mags, b_mags, denoms, cfos = [], [], [], []
        correct = classified = gated = 0
        for r in res:
            sid = int(r["source_index"])
            cls = int(r["class_index"])
            rx_burst, _ = R.load_burst(cap, sid)
            est = R.estimate_public_reference_fix2(rx_burst)
            a_mags.append(abs(est["a"]))
            b_mags.append(abs(est["b"]))
            denoms.append(abs(est["a"]) ** 2 - abs(est["b"]) ** 2)
            cfos.append(est["coarse_cfo_hz"])
            if int(r["gated"]):
                gated += 1
            if int(r["board_pred"]) >= 0:
                classified += 1
                if int(r["board_pred"]) == cls:
                    correct += 1
        return [session,
                "%.4f" % (sum(a_mags) / len(a_mags)),
                "%.5f" % (sum(b_mags) / len(b_mags)),
                "%.6f" % (sum(denoms) / len(denoms)),
                "%.1f" % min(cfos), "%.1f" % max(cfos),
                correct, gated, classified,
                "%.4f" % (correct / len(res))]

    x_rows.append(session_row("digital_file_loopback", file_capture_dir))
    x_rows.append(session_row("rf_dual_sdr", capture_dir))
    c.write_tsv(out_dir / "cross_session_validation.tsv", x_header, x_rows)

    # ---- synthetic counterexamples (injected DC -> wide-linear amplification) ----
    # The SAME DC offset is injected into a clean burst under two channels:
    #   digital-like  a=1.0  b=0    cfo=0     (file loopback -> denom ~ 1)
    #   RF-like       a=0.03 b=1e-3 cfo=-80   (dual-SDR     -> denom ~ 1e-3)
    # and the recovered tensor DC is measured for each.  The ratio shows how the
    # wide-linear inverse's denom = |a|^2-|b|^2 amplifies the same offset.
    syn_header = ["inj_dc_re", "inj_dc_im", "channel", "a_mag", "b_mag", "wl_denom",
                  "recovered_dc_re", "recovered_dc_im", "recovered_dc_mag",
                  "dc_amplification_vs_digital"]
    syn_rows = []
    wf = R.IRX.generate_waveform(3)                     # BPSK (zero-mean modulation)
    burst = R.C.deinterleave_int16(R.IRX.build_public_protocol_burst(wf))
    nn = np.arange(len(burst), dtype=np.float64)
    rf_rot = np.exp(1j * 2.0 * np.pi * (-80.0) * nn / R.FS)

    def rec_dc(rx):
        est = R.estimate_public_reference_fix2(rx)
        rec = R.recover_v2(rx, est)
        return abs(est["a"]), abs(est["b"]), \
            abs(est["a"]) ** 2 - abs(est["b"]) ** 2, complex(rec.mean())

    for inj in [(0.3 + 0.3j), (0.3 + 7.0j), (1.0 + 3.4j)]:
        r_dig = burst + inj
        r_rf = (0.030 * burst + 0.001 * np.conj(burst)) * rf_rot + inj
        ad, bd, dend, mcd = rec_dc(r_dig)
        af, bf, denf, mcf = rec_dc(r_rf)
        amp_ratio = (abs(mcf) / abs(mcd)) if abs(mcd) > 1e-12 else float("nan")
        syn_rows.append([
            "%.4f" % inj.real, "%.4f" % inj.imag, "digital", "%.4f" % ad,
            "%.5f" % bd, "%.6f" % dend, "%.4f" % mcd.real, "%.4f" % mcd.imag,
            "%.4f" % abs(mcd), "",
        ])
        syn_rows.append([
            "%.4f" % inj.real, "%.4f" % inj.imag, "rf_like", "%.4f" % af,
            "%.5f" % bf, "%.6f" % denf, "%.4f" % mcf.real, "%.4f" % mcf.imag,
            "%.4f" % abs(mcf), "%.2f" % amp_ratio,
        ])
    c.write_tsv(out_dir / "synthetic_counterexamples.tsv", syn_header, syn_rows)

    # ---- timing breakdown ----
    t_header = ["stage", "n", "mean_ms", "median_ms", "min_ms", "max_ms"]
    t_rows = []
    for stage in ["load_burst", "estimate_public_reference", "recover_v2"]:
        ts = []
        for fr in frames:
            t0 = time.perf_counter()
            if stage == "load_burst":
                R.load_burst(capture_dir, fr["sid"])
            elif stage == "estimate_public_reference":
                R.estimate_public_reference_fix2(fr["rx_burst"])
            else:
                R.recover_v2(fr["rx_burst"], fr["est"])
            ts.append((time.perf_counter() - t0) * 1000.0)
        ts = np.array(ts)
        t_rows.append([stage, len(ts), "%.3f" % ts.mean(), "%.3f" % np.median(ts),
                       "%.3f" % ts.min(), "%.3f" % ts.max()])
    c.write_tsv(out_dir / "timing_breakdown.tsv", t_header, t_rows)

    # ---- summary ----
    c.dumps_json({
        "offset_models": {
            m: {"correct": agg[m]["correct"], "classified": agg[m]["classified"],
                "n": agg[m]["n"],
                "e2e_accuracy": agg[m]["correct"] / agg[m]["n"] if agg[m]["n"] else 0.0}
            for m in MODELS
        },
        "cross_session": {r[0]: dict(zip(x_header[1:], r[1:])) for r in x_rows},
    }, out_dir / "validation_summary.json")

    print("[validate] offset-model e2e accuracy:")
    for m in MODELS:
        a = agg[m]
        print("  %-22s correct=%2d/%2d  e2e=%.4f" % (
            m, a["correct"], a["n"], a["correct"] / a["n"] if a["n"] else 0.0))
    for r in x_rows:
        print("  [cross] %-24s correct=%2d gated=%2d e2e=%s denom=%s a_mag=%s" %
              (r[0], r[6], r[7], r[9], r[3], r[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
