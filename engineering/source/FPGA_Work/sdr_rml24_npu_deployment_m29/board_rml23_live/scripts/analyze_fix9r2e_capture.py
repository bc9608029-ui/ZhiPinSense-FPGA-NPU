#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_fix9r2e_capture.py -- Route F fix9r2e: OFFLINE root-cause disambiguation of
the fix9r2d verdict `TRAINING_PAYLOAD_GAIN_MISMATCH`, using ONLY the already-saved
fix9r2d real waveforms + manifests (no board re-run, no recovery-core change).

fix9r2d answered WHAT (preamble gain does not carry to the payload). fix9r2e answers
WHY, discriminating exactly three hypotheses with quantitative measurements on the
real waveforms:

  TIME_TRANSIENT       payload complex gain varies *in time* across the payload
                       (settling/AGC transient) -> windowed gain trajectory non-flat.
  FIXED_SCALE_JUMP     channel is a clean scalar in both regions but the scalar *steps*
                       between training and payload -> trajectory flat, H(f) flat,
                       payload scalar residual ~ noise floor, g_pay != g_train.
  SPECTRAL_DEPENDENCE  channel is frequency-selective; the flat-spectrum training (ZC)
                       and the shaped payload weight H(f) differently, so their LS
                       scalar gains differ -> trajectory flat, H(f) NON-flat, and the
                       training-estimated H(f) predicts the payload gain.

Analyses (named by the task, plus one decisive test):

  A. payload-windowed complex-gain trajectory over the ACTIVE payload (zero-pad guard
     regions excluded).
  B. TX-scaling + resampling contract audit: training/payload RMS in their ACTIVE
     regions (the full-payload RMS is diluted by the guard zeros), plus SRO/CFO and the
     trajectory phase slope (residual CFO/SRO proxy).
  C. spectral response H(f) from the flat-spectrum training + prediction test: does the
     SAME LTI channel explain the payload gain?

Forward convention: g such that rx ~= g*ref, g = vdot(ref, rx)/vdot(ref, ref), matching
the board `detail::ls_gain` (capture manifest gain_mag ~ 0.014).  The fix9r2d analyzer's
`g_train/g_pay` are the INVERSE gain; forward_ratio ~ 1 / analyzer gain_ratio.

stdlib + numpy only.  Run:  python -I scripts/analyze_fix9r2e_capture.py \
    --wave-manifest route_f_fix9r2d_waveforms.tsv \
    --capture-manifest route_f_fix9r2d_capture.tsv \
    --out route_f_fix9r2e_rootcause.json
"""

import argparse
import hashlib
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_fix9r2d_capture as d2

FS = d2.FS
PERIOD = d2.PERIOD
TRAIN_LEN = d2.TRAIN_LEN
PAYLOAD_START = d2.PAYLOAD_START
PAYLOAD_LEN = d2.PAYLOAD_LEN

# Window count for the payload gain trajectory (PAYLOAD_LEN % N_WIN == 0).
N_WIN = 32
WIN = PAYLOAD_LEN // N_WIN          # 1680 samples

# A payload window is "active" (carries the modulated data, not the zero guard) when
# its reference RMS exceeds this.  Training RMS is 2048; the active payload RMS is
# ~2050; the guard windows have RMS ~0.  This is an analysis gate, not an RF gate.
ACTIVE_WIN_RMS = 100.0

# Spectral smoothing (boxcar width in FFT bins) for the |H(f)| estimate.
SPECT_SMOOTH = 24


def fwd_gain(rx, ref):
    """Forward LS complex gain g for rx ~= g*ref (g = vdot(ref,rx)/vdot(ref,ref))."""
    den = float(np.vdot(ref, ref).real)
    if den <= 0.0:
        return 0.0j
    with np.errstate(all="ignore"):
        return np.vdot(ref, rx) / den


def scalar_residual(rx, ref):
    """||rx - g*ref|| / ||g*ref|| under the forward scalar model."""
    g = fwd_gain(rx, ref)
    den = float(np.sum(np.abs(g * ref) ** 2))
    if den <= 0.0:
        return float("inf")
    return math.sqrt(float(np.sum(np.abs(rx - g * ref) ** 2)) / den)


def nmse(a, b):
    den = float(np.sum(np.abs(b) ** 2))
    if den <= 0.0:
        return float("inf")
    return float(np.sum(np.abs(a - b) ** 2)) / den


def db20(a, b):
    """20*log10(a/b), robust: b<=0 -> inf, a<=0 -> -inf (no log domain error)."""
    if b <= 0.0:
        return float("inf")
    if a <= 0.0:
        return float("-inf")
    return 20.0 * math.log10(a / b)


def active_windows(pay_ref):
    """Indices of payload windows whose reference RMS exceeds ACTIVE_WIN_RMS."""
    act = []
    for w in range(N_WIN):
        seg = pay_ref[w * WIN:(w + 1) * WIN]
        if float(np.sqrt(np.mean(np.abs(seg) ** 2))) > ACTIVE_WIN_RMS:
            act.append(w)
    return act


def rms_seg(x):
    return float(np.sqrt(np.mean(np.abs(x) ** 2))) if x.size else 0.0


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# A. payload-windowed complex-gain trajectory (active windows only)
# ---------------------------------------------------------------------------
def gain_trajectory(pay_rx, pay_ref):
    act = active_windows(pay_ref)
    mags, phases = [], []
    for w in act:
        seg_rx = pay_rx[w * WIN:(w + 1) * WIN]
        seg_ref = pay_ref[w * WIN:(w + 1) * WIN]
        g = fwd_gain(seg_rx, seg_ref)
        mags.append(abs(g))
        phases.append(math.atan2(g.imag, g.real))
    mags = np.asarray(mags, dtype=np.float64)
    phases = np.asarray(phases, dtype=np.float64)

    mag_mean = float(np.mean(mags))
    mag_std_db = 20.0 * math.log10(float(np.std(mags)) / mag_mean) if mag_mean > 0 else 0.0
    mag_pp_db = db20(float(np.max(mags)), float(np.min(mags))) if mags.size else float("inf")

    first2 = float(np.mean(mags[:2])) if mags.size >= 2 else mag_mean
    rest = float(np.mean(mags[2:])) if mags.size > 2 else mag_mean
    first_vs_rest_db = db20(first2, rest)

    idx = np.arange(mags.size, dtype=np.float64)
    mag_db = 20.0 * np.log10(mags + 1e-300)
    mag_slope_db = float(np.polyfit(idx, mag_db, 1)[0]) if mags.size >= 2 else 0.0

    ph_u = np.unwrap(phases)
    ph_slope = float(np.polyfit(idx, ph_u, 1)[0]) if phases.size >= 2 else 0.0

    return {
        "n_active_windows": int(mags.size),
        "n_windows": N_WIN,
        "window_len": WIN,
        "mag_mean": mag_mean,
        "mag_std_db": mag_std_db,
        "mag_pp_db": mag_pp_db,
        "first_vs_rest_db": first_vs_rest_db,
        "mag_slope_db_per_win": mag_slope_db,
        "phase_slope_deg_per_win": ph_slope,
    }


# ---------------------------------------------------------------------------
# C. spectral response H(f) from the flat-spectrum training + prediction test
# ---------------------------------------------------------------------------
def spectral_analysis(train_rx, train_ref, pay_rx, pay_ref):
    N = TRAIN_LEN
    A = float(np.mean(np.abs(train_ref)))        # ZC constant modulus ~ 2048
    X = np.fft.fft(train_ref)
    Y = np.fft.fft(train_rx)
    N_A2 = float(N) * A * A                     # |X[k]|^2 == N*A^2 for all k (flat ZC)

    # smoothed |H(f)|^2 from the received-training power spectrum, minus DC/Nyquist.
    Py = np.abs(Y) ** 2
    kernel = np.ones(SPECT_SMOOTH, dtype=np.float64) / SPECT_SMOOTH
    Py_s = np.convolve(Py, kernel, mode="same")
    H2 = Py_s / N_A2
    valid = np.arange(1, N - 1)
    H2_v = H2[valid]
    h_ripple_db = 10.0 * math.log10(float(np.max(H2_v)) / float(np.min(H2_v))) \
        if np.min(H2_v) > 0 else float("inf")

    half = N // 2
    low = valid[(valid >= 1) & (valid < half)]
    high = valid[(valid >= half) & (valid < N)]
    low_vs_high_db = 10.0 * math.log10(float(np.mean(H2[low])) / float(np.mean(H2[high]))) \
        if float(np.mean(H2[high])) > 0 else float("inf")

    # Channel impulse response from the flat-spectrum training: h = IFFT(conj(X)*Y)/(N*A^2).
    h_est = np.fft.ifft(np.conj(X) * Y) / N_A2

    # Predict payload under "same LTI channel": pay_rx_pred = h * pay_ref (linear conv).
    nfft = 1 << (PAYLOAD_LEN + TRAIN_LEN - 1 - 1).bit_length()
    Hpad = np.fft.fft(h_est, nfft)
    Xpay = np.fft.fft(pay_ref, nfft)
    pay_rx_pred = np.fft.ifft(Hpad * Xpay)[:PAYLOAD_LEN]

    g_pay_meas = fwd_gain(pay_rx, pay_ref)
    g_pay_pred = fwd_gain(pay_rx_pred, pay_ref)
    pred_error_db = db20(abs(g_pay_meas), abs(g_pay_pred))

    # Fit quality over the ACTIVE payload only (the guard is pure noise floor).
    act = np.zeros(PAYLOAD_LEN, dtype=bool)
    for w in active_windows(pay_ref):
        act[w * WIN:(w + 1) * WIN] = True
    fir_nmse = nmse(pay_rx[act], pay_rx_pred[act])
    g_train = fwd_gain(train_rx, train_ref)
    scalar_carry_nmse = nmse(pay_rx[act], g_train * pay_ref[act])

    return {
        "h_ripple_db": h_ripple_db,
        "h_low_vs_high_db": low_vs_high_db,
        "g_pay_meas_mag": abs(g_pay_meas),
        "g_pay_pred_mag": abs(g_pay_pred),
        "g_pay_meas_phase_deg": math.degrees(math.atan2(g_pay_meas.imag, g_pay_meas.real)),
        "g_pay_pred_phase_deg": math.degrees(math.atan2(g_pay_pred.imag, g_pay_pred.real)),
        "pred_error_db": pred_error_db,
        "fir_nmse": fir_nmse,
        "scalar_carry_nmse": scalar_carry_nmse,
    }


# ---------------------------------------------------------------------------
# B. TX-scaling + resampling contract audit
# ---------------------------------------------------------------------------
def tx_resample_contract(train_ref, pay_ref, train_rx, pay_rx, meta, traj):
    act = np.zeros(PAYLOAD_LEN, dtype=bool)
    for w in active_windows(pay_ref):
        act[w * WIN:(w + 1) * WIN] = True

    tx_train_rms = rms_seg(train_ref)
    tx_pay_active_rms = rms_seg(pay_ref[act])
    tx_pay_full_rms = rms_seg(pay_ref)
    rx_train_rms = rms_seg(train_rx)
    rx_pay_active_rms = rms_seg(pay_rx[act])
    rx_pay_full_rms = rms_seg(pay_rx)

    # A flat scalar channel preserves rx_pay/rx_train == tx_pay/tx_train.  Using the
    # ACTIVE payload RMS (not the guard-diluted full RMS) isolates the real mismatch.
    tx_ratio = tx_pay_active_rms / tx_train_rms
    rx_ratio = rx_pay_active_rms / rx_train_rms
    excess_db = db20(rx_ratio, tx_ratio)

    return {
        "tx_train_rms": tx_train_rms,
        "tx_pay_active_rms": tx_pay_active_rms,
        "tx_pay_full_rms": tx_pay_full_rms,
        "rx_train_rms": rx_train_rms,
        "rx_pay_active_rms": rx_pay_active_rms,
        "rx_pay_full_rms": rx_pay_full_rms,
        "tx_ratio": tx_ratio,
        "rx_ratio": rx_ratio,
        "excess_db": excess_db,
        "sro_ppm": meta["sro_ppm"],
        "cfo_hz": meta["cfo_hz"],
        "payload_phase_slope_deg_per_win": traj["phase_slope_deg_per_win"],
    }


# ---------------------------------------------------------------------------
# Root-cause decision (quantitative; analysis-only, not an RF gate).
# ---------------------------------------------------------------------------
def decide_root_cause(traj, spec, g_train, g_pay, residual_pay):
    fwd_ratio = abs(g_pay) / abs(g_train) if abs(g_train) > 0 else float("inf")

    # TIME_TRANSIENT: payload gain varies in time (settling/ramp inside the payload).
    if traj["mag_pp_db"] > 3.0 or abs(traj["first_vs_rest_db"]) > 3.0 \
            or abs(traj["mag_slope_db_per_win"]) > 0.5:
        return "TIME_TRANSIENT"

    # SPECTRAL_DEPENDENCE: the training-estimated H(f) PREDICTS the payload gain
    # (the 8 dB gap lives in H(f), e.g. a passband tilt / near-DC excess).  The
    # discriminator is the prediction error, not the raw H(f) ripple -- a flat-ish
    # but mismatched H(f) can still predict a real frequency-dependent gap.
    if abs(spec["pred_error_db"]) < 1.5 and not (0.9 <= fwd_ratio <= 1.1):
        return "SPECTRAL_DEPENDENCE"

    # FIXED_SCALE_JUMP: the payload is a clean scalar (low residual) and the gain gap
    # is NOT explained by H(f) (large prediction error) -> a clean, settled scalar step
    # between the preamble and the payload.
    if residual_pay < 0.05 and abs(spec["pred_error_db"]) >= 1.5 \
            and not (0.9 <= fwd_ratio <= 1.1):
        return "FIXED_SCALE_JUMP"

    return "NOT_IDENTIFIED"


def analyze_one(fn, w, meta, base):
    train_ref, train_rx = w["train_ref"], w["train_rx"]
    pay_ref, pay_rx = w["pay_ref"], w["pay_rx"]

    g_train = fwd_gain(train_rx, train_ref)
    g_pay = fwd_gain(pay_rx, pay_ref)
    fwd_ratio = abs(g_pay) / abs(g_train) if abs(g_train) > 0 else float("inf")
    phase_diff = math.degrees(math.atan2((g_pay / g_train).imag, (g_pay / g_train).real)) \
        if abs(g_train) > 0 else 0.0
    residual_train = scalar_residual(train_rx, train_ref)

    act = np.zeros(PAYLOAD_LEN, dtype=bool)
    for ww in active_windows(pay_ref):
        act[ww * WIN:(ww + 1) * WIN] = True
    residual_pay = scalar_residual(pay_rx[act], pay_ref[act])

    # Repeating-pattern proof (correct): the SAME preamble/payload gain recurs in BOTH
    # adjacent cycles -> deterministic, not a one-time settling.  A settling transient
    # would differ between cycles; here the preamble gain stays ~g_train and the payload
    # gain stays ~g_pay in both cycle0 and cycle1 (d2 already reports corr > 0.99).
    circ = int(meta["timing_offset"]) % PERIOD
    cyc0_train = d2.circular_slice(w["cycle0"], circ, TRAIN_LEN)
    cyc1_train = d2.circular_slice(w["cycle1"], circ, TRAIN_LEN)
    cyc0_pay = d2.circular_slice(w["cycle0"], circ + PAYLOAD_START, PAYLOAD_LEN)
    cyc1_pay = d2.circular_slice(w["cycle1"], circ + PAYLOAD_START, PAYLOAD_LEN)
    g_c0_tr = fwd_gain(cyc0_train, train_ref)
    g_c1_tr = fwd_gain(cyc1_train, train_ref)
    g_c0_pay = fwd_gain(cyc0_pay, pay_ref)
    g_c1_pay = fwd_gain(cyc1_pay, pay_ref)

    traj = gain_trajectory(pay_rx, pay_ref)
    spec = spectral_analysis(train_rx, train_ref, pay_rx, pay_ref)
    contract = tx_resample_contract(train_ref, pay_ref, train_rx, pay_rx, meta, traj)
    cause = decide_root_cause(traj, spec, g_train, g_pay, residual_pay)

    m = {
        "g_train_mag": abs(g_train),
        "g_train_phase_deg": math.degrees(math.atan2(g_train.imag, g_train.real)),
        "g_pay_mag": abs(g_pay),
        "g_pay_phase_deg": math.degrees(math.atan2(g_pay.imag, g_pay.real)),
        "forward_gain_ratio": fwd_ratio,
        "phase_diff_deg": phase_diff,
        "residual_train": residual_train,
        "residual_pay": residual_pay,
        "cycle_preamble_gain_mags": [abs(g_c0_tr), abs(g_c1_tr)],
        "cycle_payload_gain_mags": [abs(g_c0_pay), abs(g_c1_pay)],
        "trajectory": traj,
        "spectral": spec,
        "contract": contract,
        "root_cause": cause,
    }
    return m


# ---------------------------------------------------------------------------
# Real-data mode.
# ---------------------------------------------------------------------------
def load_verified(fn, waves, base):
    problems = []
    w = {}
    for kind, internal in d2.KIND_MAP.items():
        e = waves[kind]
        path = os.path.join(base, os.path.basename(e["path"])) if not os.path.isabs(e["path"]) \
            else e["path"]
        with open(path, "rb") as f:
            raw = f.read()
        if sha256_bytes(raw) != e["sha256"]:
            problems.append("%s/%s sha256 mismatch (host file != manifest)" % (fn, kind))
            continue
        x = np.frombuffer(raw, dtype="<f4")
        if x.size % 2 != 0:
            problems.append("%s/%s odd float count" % (fn, kind))
            continue
        w[internal] = (x[0::2] + 1j * x[1::2]).astype(np.complex128)
    return w, problems


def run(wave_path, capture_path, base):
    waves = d2.read_waveform_manifest(wave_path)
    caps = d2.read_capture_manifest(capture_path)

    problems = d2.acceptance_problems(waves, caps)
    if problems:
        for p in problems:
            print("  FIX9R2E_ACCEPTANCE_REJECTED: %s" % p)
        return {"accepted": False, "problems": problems, "per_file": []}

    results = []
    for fn in sorted(waves):
        w, wprobs = load_verified(fn, waves[fn], base)
        if wprobs:
            problems.extend(wprobs)
            continue
        if sorted(w) != sorted(d2.KIND_MAP.values()):
            problems.append("%s: internal keys incomplete" % fn)
            continue
        m = analyze_one(fn, w, caps[fn], base)
        results.append({"file_name": fn, "metrics": m})

        t = m["trajectory"]
        s = m["spectral"]
        c = m["contract"]
        print("FIX9R2E_SAMPLE file=%s" % fn)
        print("FIX9R2E_GAIN_TRAJECTORY file=%s n_active=%d mag_mean=%.6g "
              "mag_std_db=%.3f mag_pp_db=%.3f first_vs_rest_db=%.3f "
              "mag_slope_db_per_win=%.4f phase_slope_deg_per_win=%.4f"
              % (fn, t["n_active_windows"], t["mag_mean"], t["mag_std_db"],
                 t["mag_pp_db"], t["first_vs_rest_db"], t["mag_slope_db_per_win"],
                 t["phase_slope_deg_per_win"]))
        print("FIX9R2E_SPECTRAL file=%s h_ripple_db=%.3f h_low_vs_high_db=%.3f "
              "pred_error_db=%.3f fir_nmse=%.4f scalar_carry_nmse=%.4f"
              % (fn, s["h_ripple_db"], s["h_low_vs_high_db"],
                 s["pred_error_db"], s["fir_nmse"], s["scalar_carry_nmse"]))
        print("FIX9R2E_TXSCALE file=%s tx_train_rms=%.3f tx_pay_active_rms=%.3f "
              "tx_pay_full_rms=%.3f rx_train_rms=%.3f rx_pay_active_rms=%.3f "
              "excess_db=%.3f"
              % (fn, c["tx_train_rms"], c["tx_pay_active_rms"], c["tx_pay_full_rms"],
                 c["rx_train_rms"], c["rx_pay_active_rms"], c["excess_db"]))
        print("FIX9R2E_RESAMPLE file=%s sro_ppm=%.6g cfo_hz=%.6g "
              "payload_phase_slope_deg_per_win=%.4f"
              % (fn, c["sro_ppm"], c["cfo_hz"], c["payload_phase_slope_deg_per_win"]))
        print("FIX9R2E_GAINS file=%s g_train_mag=%.6g g_pay_mag=%.6g "
              "forward_gain_ratio=%.4f phase_diff_deg=%.3f residual_train=%.4f "
              "residual_pay=%.4f"
              % (fn, m["g_train_mag"], m["g_pay_mag"], m["forward_gain_ratio"],
                 m["phase_diff_deg"], m["residual_train"], m["residual_pay"]))
        print("FIX9R2E_TAIL_PREAMBLE file=%s cycle_preamble_gain_mags=[%.6g, %.6g] "
              "cycle_payload_gain_mags=[%.6g, %.6g]"
              % (fn, m["cycle_preamble_gain_mags"][0], m["cycle_preamble_gain_mags"][1],
                 m["cycle_payload_gain_mags"][0], m["cycle_payload_gain_mags"][1]))
        print("FIX9R2E_ROOT_CAUSE file=%s cause=%s" % (fn, m["root_cause"]))

    if problems:
        return {"accepted": False, "problems": problems, "per_file": results}

    return {"accepted": True, "problems": [], "per_file": results}


def main():
    ap = argparse.ArgumentParser(description="fix9r2e root-cause disambiguation")
    ap.add_argument("--wave-manifest", help="route_f_fix9r2d_waveforms.tsv")
    ap.add_argument("--capture-manifest", help="route_f_fix9r2d_capture.tsv")
    ap.add_argument("--base", default=".", help="directory containing the .f32 files")
    ap.add_argument("--out", help="write JSON results here")
    args = ap.parse_args()

    if not (args.wave_manifest and args.capture_manifest):
        ap.error("both --wave-manifest and --capture-manifest required")

    outcome = run(args.wave_manifest, args.capture_manifest, args.base)
    results = outcome["per_file"]

    if not outcome["accepted"]:
        print("FIX9R2E_ACCEPTANCE result=REJECTED (%d problem(s))" % len(outcome["problems"]))
        return 2

    print("FIX9R2E_ACCEPTANCE result=PASS")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(outcome, f, indent=2, sort_keys=True)
        print("wrote %s" % args.out)
    causes = set(r["metrics"]["root_cause"] for r in results)
    run_cause = next(iter(causes)) if len(causes) == 1 else "NOT_IDENTIFIED"
    print("FIX9R2E_ROOT_CAUSE cause=%s (files=%d, distinct=%d)"
          % (run_cause, len(results), len(causes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
