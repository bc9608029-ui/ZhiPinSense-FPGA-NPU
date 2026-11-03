#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_fix9r2b_residuals.py -- Route F fix9r2c Phase 1: OFFLINE root-cause
quantifier for the R8 residual (training_corr ~ 0.974, training_residual ~ 0.23).

fix9r2b Phase 1 captures 5 waveforms per R8 diagnostic file (expected_training,
aligned_rx_training, training_error, expected_payload, provisional_recovered_payload)
and NOTHING else.  This analyzer reads those raw .f32 files and QUANTIFIES the five
candidate causes of the scalar-model residual, so a minimal fix is chosen only after
a quantitative root cause is established (discipline: no equalizer before a named,
measured cause).

fix9r2c (this revision) FIXES three complex-math bugs that made the fix9r2b analyzer
mis-report the root cause as DC_IQ_IMBALANCE with scalar_only_residual ~= 2.0 (the
board's true scalar residual is ~0.22):

  B1  scalar_fit conjugate-direction bug:  a = vdot(rx, ref) is conj(g_true), which
      rotates the model ~180 deg and inflates the residual to ~2.0.  Fixed to the
      documented model direction below.
  B2  payload_metrics float() complex-discard bug:  float(np.vdot(x, p)) drops the
      imaginary part, scaling corr by |cos(arg(g))|.  Fixed to abs() of the complex.
  B3  _band_mask two disjoint sidebands: unwrap/gradient/ptp/polyfit crossed the DC
      gap and produced a spurious group_delay_ripple_samples ~= 62.  Fixed to per-
      sideband processing (never cross DC), preserving bilateral spectrum for the
      IQ-imbalance diagnosis.

Scalar-model direction (fixed and documented, NOT just a vdot swap):

      observed_rx = g * expected_ref          (g == forward complex gain)
      g = vdot(expected_ref, observed_rx) / vdot(expected_ref, expected_ref)
          == sum(conj(ref) * rx) / sum(|ref|^2)   (matches iqrfrec::detail::ls_gain)

  The board's recovery applies 1/g (a_inv = conj(g)/|g|^2).  This analyzer only
  PRODUCES the forward g for comparison; it never drives the recovery.

Candidate models M0-M4 are compared by CONTINUOUS BLOCKED cross-validation (never
even/odd, never random K-fold): front-fit -> back-validate and back-fit ->
front-validate, with a guard >= FIR half-length between the estimation and validation
segments so adjacent-sample convolution leakage cannot deflate the validation
residual.  Cross-capture validation separates each capture's complex scalar g from
the COMMON normalized distortion kernel (fractional delay / b:a / IRR / FIR shape).

stdlib + numpy only.  Run with:  python -I scripts/analyze_fix9r2b_residuals.py ...
"""

import argparse
import json
import math
import sys
import warnings

import numpy as np

FS = 2560000.0

# Occupied-band edges (fraction of Nyquist, i.e. normalized |f| in cycles/sample).
# The ZC preamble is a CAZAC with unit FFT magnitude at every bin, but the TX/RX
# anti-alias filters roll off near DC and Nyquist, so ripple/group-delay metrics are
# restricted to the central band.  The POSITIVE and NEGATIVE sidebands are processed
# SEPARATELY (a real-channel H is conjugate-symmetric, but I/Q imbalance breaks that,
# so both must be kept); never unwrap/gradient across the DC gap (bug B3).
BAND_LO = 0.05
BAND_HI = 0.45

# Continuous blocked-CV geometry (documented).  n=1024 training samples.
CV_MID = 512          # estimation/validation split point
CV_GUARD = 16         # gap between estimation and validation (>= FIR half-length 5)
CV_MARGIN = 5         # conv-boundary samples dropped at each validation-segment edge

# FIR tap candidate set (Task C): pick the SHORTEST that clears the residual gate,
# using TRAINING blocked-CV only -- never expected_payload / class / final prediction.
FIR_TAPS = [3, 5, 7, 9, 11]

# Thresholds (documented; tunable).
T_SCALAR_FLOOR = 1e-9     # scalar residual below this == NO_RESIDUAL
T_CENTRAL_RATIO = 0.60    # central residual / scalar below this -> boundary suspect
T_BOUNDARY_RATIO = 2.0    # edge error / central error above this -> transient
T_DCIQ_RATIO = 0.50       # dc_iq_residual / scalar below this -> DC/IQ imbalance
T_FD_RATIO = 0.50         # fractional_delay_residual / scalar below -> pure fractional delay
T_AMP_RIPPLE_DB = 0.5     # |H| p-p (dB) above this -> amplitude ripple
T_PHASE_RIPPLE_DEG = 3.0  # phase non-linearity p-p (deg) above this -> phase ripple
T_GROUP_DELAY_PP = 0.05   # group-delay p-p (samples) above this -> group delay
# Root-cause "proven" requires the winning validation residual to clear this fraction
# of the scalar residual (stricter than the cause-selection ratio) AND pass in both
# blocked directions AND across captures.
T_PROVEN_RATIO = 0.50

# Board ground truth from the fix9r2c task book section 0 (equivalence-gate constants,
# keyed by the manifest's file_name).  These are NOT read from the waveforms; the
# analyzer independently recomputes corr/residual and asserts agreement.
BOARD_TRUTH = {
    "quantized_d2_2p56m_000006.ci16": {"corr": 0.972983, "residual": 0.237286},  # BPSK
    "quantized_d2_2p56m_000002.ci16": {"corr": 0.976160, "residual": 0.222355},  # 4ASK
}
EQ_TOL = 1e-4


# ---------------------------------------------------------------------------
# Warning guardrails (bug B2): upgrade ComplexWarning to an error, with a SAFE
# getattr fallback across NumPy versions (1.23 exposes np.ComplexWarning; 1.24 moved
# it to numpy.exceptions).  Never assume np.exceptions exists.
# ---------------------------------------------------------------------------
def _complex_warning_category():
    exc = getattr(np, "exceptions", None)
    if exc is not None:
        cw = getattr(exc, "ComplexWarning", None)
        if cw is not None:
            return cw
    return getattr(np, "ComplexWarning", None)


_COMPLEX_WARNING = _complex_warning_category()
if _COMPLEX_WARNING is not None:
    warnings.filterwarnings("error", category=_COMPLEX_WARNING)


def load_f32(path):
    """Load interleaved little-endian float32 [I0,Q0,I1,Q1,...] -> complex128."""
    raw = np.fromfile(path, dtype="<f4")
    if raw.size % 2 != 0:
        raise ValueError("%s: odd float count %d (not interleaved IQ)" % (path, raw.size))
    return (raw[0::2] + 1j * raw[1::2]).astype(np.complex128)


def rms(x):
    return float(np.sqrt(np.mean(np.abs(x) ** 2))) if x.size else 0.0


# ---------------------------------------------------------------------------
# Scalar model (bug B1 fixed): documented direction observed_rx = g * expected_ref.
# ---------------------------------------------------------------------------
def scalar_fit(rx, ref):
    """LS forward complex gain g for rx ~ g*ref; returns (g, residual, model)."""
    den = float(np.vdot(ref, ref).real)   # vdot returns complex128; sum(|ref|^2) is real
    if den <= 0.0:
        return 0.0j, float("inf"), None
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        g = np.vdot(ref, rx) / den          # == sum(conj(ref)*rx) / sum(|ref|^2)
        model = g * ref
        res = math.sqrt(float(np.sum(np.abs(rx - model) ** 2)) /
                        float(np.sum(np.abs(model) ** 2)))
    return g, res, model


def normalized_corr(rx, ref):
    """Magnitude-normalized cross-correlation |sum(rx*conj(ref))| / (||rx||*||ref||)."""
    den = math.sqrt(float(np.sum(np.abs(rx) ** 2)) * float(np.sum(np.abs(ref) ** 2)))
    if den <= 0.0:
        return 0.0
    return float(abs(np.vdot(ref, rx))) / den


def fft_delay(ref, tau):
    """Return ref delayed by tau samples (fractional, via FFT phase shift)."""
    n = ref.size
    k = np.fft.fftfreq(n)
    return np.fft.ifft(np.fft.fft(ref) * np.exp(-1j * 2.0 * math.pi * tau * k))


def _pos_mask(n):
    f = np.fft.fftfreq(n)
    return (f >= BAND_LO) & (f <= BAND_HI)


def _neg_mask(n):
    f = np.fft.fftfreq(n)
    return (f <= -BAND_LO) & (f >= -BAND_HI)


def _phase_slope(rx, ref, mask):
    """Phase-slope (cycles/sample) of H = Xf/Rf over a single contiguous band."""
    n = ref.size
    Rf = np.fft.fft(ref)
    Xf = np.fft.fft(rx)
    f = np.fft.fftfreq(n)
    with np.errstate(divide="ignore", invalid="ignore"):
        H = np.where(np.abs(Rf) > 1e-9 * np.max(np.abs(Rf)), Xf / Rf, 0.0j)
    ph = np.unwrap(np.angle(H[mask]))
    f_sel = f[mask]
    if f_sel.size < 2:
        return 0.0
    slope, _ = np.polyfit(f_sel, ph, 1)
    return -slope / (2.0 * math.pi)   # slope = -2*pi*tau -> tau = -slope/(2*pi)


def fractional_delay_estimate(rx, ref):
    """Per-sideband fractional delay (samples); returns
    (tau_pos, tau_neg, tau_avg, residual_after_correction)."""
    n = ref.size
    tau_pos = _phase_slope(rx, ref, _pos_mask(n))
    tau_neg = _phase_slope(rx, ref, _neg_mask(n))
    tau_avg = 0.5 * (tau_pos + tau_neg)
    ref_shift = fft_delay(ref, tau_avg)
    _, res, _ = scalar_fit(rx, ref_shift)
    return float(np.clip(tau_pos, -0.5, 0.5)), \
        float(np.clip(tau_neg, -0.5, 0.5)), \
        float(np.clip(tau_avg, -0.5, 0.5)), res


def dc_iq_fit(rx, ref):
    """Fit rx ~ a*ref + b*conj(ref) + c (DC offset c, I/Q imbalance b).
    Returns dict with dc_offset_rel, image_rejection_db, b_over_a, residual."""
    n = ref.size
    A = np.column_stack([ref, np.conj(ref), np.ones(n, dtype=np.complex128)])
    coef, _, _, _ = np.linalg.lstsq(A, rx, rcond=None)
    a, b, c = coef[0], coef[1], coef[2]
    model = a * ref + b * np.conj(ref) + c
    den = float(np.sum(np.abs(model) ** 2))
    res = math.sqrt(float(np.sum(np.abs(rx - model) ** 2)) / den) if den > 0 else float("inf")
    ref_rms = rms(ref)
    dc_rel = abs(c) / ref_rms if ref_rms > 0 else 0.0
    img_db = (20.0 * math.log10(abs(a) / abs(b))
              if abs(b) > 1e-15 and abs(a) > 0 else float("inf"))
    b_over_a = (b / a) if abs(a) > 1e-15 else complex(float("inf"), float("inf"))
    return {"dc_offset_rel": float(dc_rel), "image_rejection_db": float(img_db),
            "b_over_a": complex(b_over_a), "residual": res, "a": a, "b": b, "c": c}


def _fir_design(ref, ntap):
    """Linear-convolution design matrix (n, ntap) for a centered FIR, zero-padded at
    the window edges (never circular -- circular roll leaks across the blocked-CV
    estimation/validation boundary).  model[k] = sum_j h[j] * ref[k + half - j]."""
    n = ref.size
    half = ntap // 2
    A = np.zeros((n, ntap), dtype=np.complex128)
    for j in range(ntap):
        shift = half - j
        lo = max(0, -shift)
        hi = min(n, n - shift)
        if hi > lo:
            A[lo:hi, j] = ref[lo + shift:hi + shift]
    return A


def fir_fit(rx_seg, ref_seg, ntap):
    """LS centered-FIR fit on a segment -> (residual, h, model)."""
    A = _fir_design(ref_seg, ntap)
    h, _, _, _ = np.linalg.lstsq(A, rx_seg, rcond=None)
    model = A @ h
    den = float(np.sum(np.abs(model) ** 2))
    res = math.sqrt(float(np.sum(np.abs(rx_seg - model) ** 2)) / den) if den > 0 else float("inf")
    return res, h, model


def band_response(rx, ref, a):
    """Per-sideband |H| p-p (dB), phase non-linearity p-p (deg), group-delay p-p
    (samples), where H = FFT(rx)/FFT(ref) with the scalar gain removed.  Each sideband
    is unwrapped / polyfit / gradient'd independently (never across DC)."""
    n = ref.size
    Rf = np.fft.fft(ref)
    Xf = np.fft.fft(rx)
    f = np.fft.fftfreq(n)
    with np.errstate(divide="ignore", invalid="ignore"):
        H = np.where(np.abs(Rf) > 1e-9 * np.max(np.abs(Rf)), Xf / Rf, 0.0j)
    H = H / a if abs(a) > 1e-15 else H
    out = {}
    for tag, mask in (("pos", _pos_mask(n)), ("neg", _neg_mask(n))):
        mag_db = 20.0 * np.log10(np.abs(H[mask]) + 1e-15)
        amp_pp_db = float(np.ptp(mag_db))
        ph = np.unwrap(np.angle(H[mask]))
        f_sel = f[mask]
        slope, intercept = np.polyfit(f_sel, ph, 1)
        lin = slope * f_sel + intercept
        ph_pp_deg = float(np.ptp(np.rad2deg(ph - lin)))
        # group-delay ripple: from a SMOOTH low-order fit of the non-linear phase,
        # NOT np.gradient on the raw per-bin phase.  np.gradient amplifies per-bin
        # phase noise into a spurious ~62-sample group delay (0.35 rad/bin / (2*pi*
        # 1/1024) ~ 57 samples); a degree-5 polynomial captures the smooth frequency-
        # dependent delay while smoothing out the per-bin noise.
        coef = np.polyfit(f_sel, ph - lin, 5)
        dcoef = np.polyder(coef)
        gd = -(1.0 / (2.0 * math.pi)) * np.polyval(dcoef, f_sel)
        gd_pp = float(np.ptp(gd))
        out[tag] = {"amp_pp_db": amp_pp_db, "phase_pp_deg": ph_pp_deg,
                    "gd_pp_samples": gd_pp}
    return out


# ---------------------------------------------------------------------------
# Continuous blocked cross-validation (Task C): front-fit -> back-validate and
# back-fit -> front-validate, guard + margin, per-model validation residual.
# ---------------------------------------------------------------------------
def _residual_at(rx, model, sl):
    num = float(np.sum(np.abs(rx[sl] - model[sl]) ** 2))
    den = float(np.sum(np.abs(model[sl]) ** 2))
    return math.sqrt(num / den) if den > 0 else float("inf")


def _m0_fit_predict(est_rx, est_ref, full_rx, full_ref, est_slice):
    g = np.vdot(est_ref, est_rx) / float(np.vdot(est_ref, est_ref).real)
    return g * full_ref


def _m1_fit_predict(est_rx, est_ref, full_rx, full_ref, est_slice):
    # Fractional delay tau is a single FRAME-LEVEL parameter (1 real DOF), estimated
    # once per frame from the full-preamble phase slope ("逐帧估 τ").  The blocked-CV
    # cross-validates only the per-segment complex scalar g (fit on est, validated on
    # val).  Estimating tau from a 512-sample half is numerically fragile because the
    # FFT delay is circular and truncation breaks it.
    tau = 0.5 * (_phase_slope(full_rx, full_ref, _pos_mask(full_ref.size)) +
                 _phase_slope(full_rx, full_ref, _neg_mask(full_ref.size)))
    delayed_full = fft_delay(full_ref, tau)
    delayed_est = delayed_full[est_slice]
    g = np.vdot(delayed_est, est_rx) / float(np.vdot(delayed_est, delayed_est).real)
    return g * delayed_full


def _m2_fit_predict(est_rx, est_ref, full_rx, full_ref, est_slice):
    n = est_ref.size
    A = np.column_stack([est_ref, np.conj(est_ref), np.ones(n, dtype=np.complex128)])
    coef, _, _, _ = np.linalg.lstsq(A, est_rx, rcond=None)
    a, b, c = coef[0], coef[1], coef[2]
    return a * full_ref + b * np.conj(full_ref) + c


def _m3_fit_predict(est_rx, est_ref, full_rx, full_ref, est_slice, ntap):
    A = _fir_design(est_ref, ntap)
    h, _, _, _ = np.linalg.lstsq(A, est_rx, rcond=None)
    return _fir_design(full_ref, ntap) @ h


def blocked_cv(rx, ref, fit_predict):
    """Continuous blocked CV: returns (res_fwd, res_bwd, mean).
    fit_predict(est_rx, est_ref, full_rx, full_ref, est_slice) -> model_on_full_ref."""
    n = ref.size
    half = CV_MARGIN
    # forward: fit [0:CV_MID], validate [CV_MID+CV_GUARD : n]
    val_f = slice(CV_MID + CV_GUARD, n)
    est_f = slice(0, CV_MID)
    model_f = fit_predict(rx[est_f], ref[est_f], rx, ref, est_f)
    res_f = _residual_at(rx, model_f, slice(val_f.start + half, val_f.stop - half))
    # backward: fit [CV_MID:n], validate [0 : CV_MID-CV_GUARD]
    val_b = slice(0, CV_MID - CV_GUARD)
    est_b = slice(CV_MID, n)
    model_b = fit_predict(rx[est_b], ref[est_b], rx, ref, est_b)
    res_b = _residual_at(rx, model_b, slice(val_b.start + half, val_b.stop - half))
    return res_f, res_b, 0.5 * (res_f + res_b)


def model_table(rx, ref):
    """Blocked-CV validation residuals for M0-M3 (with FIR tap set) on (rx, ref)."""
    t = {}
    t["m0"] = blocked_cv(rx, ref, _m0_fit_predict)
    t["m1"] = blocked_cv(rx, ref, _m1_fit_predict)
    t["m2"] = blocked_cv(rx, ref, _m2_fit_predict)
    m3 = {}
    for ntap in FIR_TAPS:
        m3["m3_%d" % ntap] = blocked_cv(
            rx, ref, lambda erx, eref, frx, fref, es, _n=ntap:
            _m3_fit_predict(erx, eref, frx, fref, es, _n))
    t["m3"] = m3
    return t


def boundary_metrics(rx, ref, g):
    """Boundary transient: same scalar model applied to central 75% vs edge
    12.5%+12.5%; returns (central_residual, boundary_ratio)."""
    n = ref.size
    m = n // 8
    err = rx - g * ref
    core_err_rms = rms(err[m:n - m])
    edge_idx = np.concatenate([np.arange(0, m), np.arange(n - m, n)])
    edge_err_rms = rms(err[edge_idx])
    model_core_rms = rms((g * ref)[m:n - m])
    central_res = (core_err_rms / model_core_rms) if model_core_rms > 0 else float("inf")
    boundary_ratio = (edge_err_rms / core_err_rms) if core_err_rms > 1e-12 else 1.0
    return central_res, boundary_ratio


# ---------------------------------------------------------------------------
# Payload metrics (bug B2 fixed + Task I four-way breakdown).
# ---------------------------------------------------------------------------
def payload_metrics(recovered, expected):
    """Magnitude-normalized shape corr + the raw/optimal-scale NMSE split + gain error.

    shape_corr            magnitude-normalized cross-correlation [0,1] (shape only)
    raw_nmse              ||x - p||^2 / ||p||^2          (includes recovery gain error)
    optimal_scale_nmse    min_g ||g*x - p||^2 / ||p||^2  (shape-preservation floor)
    gain_ratio / gain_error_db   optimal complex gain g* = vdot(x,p)/vdot(x,x)
    """
    n = min(recovered.size, expected.size)
    if n == 0:
        return {"computed": False, "shape_corr": 0.0, "raw_nmse": 0.0,
                "optimal_scale_nmse": 0.0, "gain_ratio": 0.0, "gain_error_db": 0.0}
    x = recovered[:n]
    p = expected[:n]
    den_ref = float(np.sum(np.abs(p) ** 2))
    den_x = float(np.sum(np.abs(x) ** 2))
    if den_ref <= 0.0:
        return {"computed": False, "shape_corr": 0.0, "raw_nmse": 0.0,
                "optimal_scale_nmse": 0.0, "gain_ratio": 0.0, "gain_error_db": 0.0}
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        num = abs(np.vdot(p, x))                       # complex magnitude, not float()
    shape_corr = float(num) / math.sqrt(den_x * den_ref) if den_x > 0 else 0.0
    raw_nmse = float(np.sum(np.abs(x - p) ** 2)) / den_ref
    # optimal scale g* that makes g*x best match p (LS): g* = vdot(x,p)/vdot(x,x)
    gstar = np.vdot(x, p) / den_x if den_x > 0 else 0.0j
    scaled = gstar * x
    optimal_scale_nmse = float(np.sum(np.abs(scaled - p) ** 2)) / den_ref
    gain_ratio = abs(gstar)
    gain_error_db = 20.0 * math.log10(gain_ratio) if gain_ratio > 0 else float("inf")
    return {"computed": True, "shape_corr": float(shape_corr), "raw_nmse": float(raw_nmse),
            "optimal_scale_nmse": float(optimal_scale_nmse),
            "gain_ratio": float(gain_ratio), "gain_error_db": float(gain_error_db)}


# ---------------------------------------------------------------------------
# Analyze one (aligned_rx_training, expected_training) pair -> full metric dict.
# ---------------------------------------------------------------------------
def analyze_training(rx, ref):
    g, scalar_res, _ = scalar_fit(rx, ref)
    corr = normalized_corr(rx, ref)
    tau_pos, tau_neg, tau_avg, fd_res = fractional_delay_estimate(rx, ref)
    dciq = dc_iq_fit(rx, ref)
    band = band_response(rx, ref, g)
    central_res, boundary_ratio = boundary_metrics(rx, ref, g)
    cv = model_table(rx, ref)

    # FIR tap selection (training blocked-CV only): shortest tap whose mean validation
    # residual clears T_PROVEN_RATIO * scalar, else the tap with the minimum mean
    # validation residual (the "best" FIR, reported even when nothing clears).
    selected_ntap = FIR_TAPS[0]
    for ntap in FIR_TAPS:
        mean_res = cv["m3"]["m3_%d" % ntap][2]
        if mean_res < T_PROVEN_RATIO * scalar_res:
            selected_ntap = ntap
            break
    best_ntap = min(FIR_TAPS, key=lambda nt: cv["m3"]["m3_%d" % nt][2])
    best_val_res = cv["m3"]["m3_%d" % best_ntap][2]

    return {
        "scalar_only_residual": scalar_res,
        "offline_training_corr": corr,
        "offline_training_residual": scalar_res,
        "gain_mag": abs(g),
        "gain_phase_deg": math.degrees(math.atan2(g.imag, g.real)),
        "fractional_delay_samples": tau_avg,
        "fractional_delay_samples_pos": tau_pos,
        "fractional_delay_samples_neg": tau_neg,
        "fractional_delay_residual": fd_res,
        "dc_offset_rel": dciq["dc_offset_rel"],
        "image_rejection_db": dciq["image_rejection_db"],
        "b_over_a_real": float(dciq["b_over_a"].real),
        "b_over_a_imag": float(dciq["b_over_a"].imag),
        "dc_iq_residual": dciq["residual"],
        "amplitude_ripple_db_pp_pos": band["pos"]["amp_pp_db"],
        "amplitude_ripple_db_pp_neg": band["neg"]["amp_pp_db"],
        "phase_ripple_deg_pp_pos": band["pos"]["phase_pp_deg"],
        "phase_ripple_deg_pp_neg": band["neg"]["phase_pp_deg"],
        "group_delay_ripple_samples_pos": band["pos"]["gd_pp_samples"],
        "group_delay_ripple_samples_neg": band["neg"]["gd_pp_samples"],
        "central_training_residual": central_res,
        "boundary_error_ratio": boundary_ratio,
        "blocked_cv": cv,
        "fir_selected_ntap": selected_ntap,
        "fir_best_ntap": best_ntap,
        "fir_best_val_residual": best_val_res,
    }


# ---------------------------------------------------------------------------
# Equivalence gate (Task B): offline corr/residual must match the board constants.
# ---------------------------------------------------------------------------
def equivalence_gate(fn, m):
    if fn not in BOARD_TRUTH:
        return {"checked": False, "pass": False, "note": "no board truth for %s" % fn}
    bt = BOARD_TRUTH[fn]
    corr_err = abs(m["offline_training_corr"] - bt["corr"])
    res_err = abs(m["offline_training_residual"] - bt["residual"])
    ok = corr_err < EQ_TOL and res_err < EQ_TOL
    return {"checked": True, "pass": ok, "board_corr": bt["corr"], "board_residual": bt["residual"],
            "corr_err": corr_err, "residual_err": res_err}


# ---------------------------------------------------------------------------
# Root-cause selection (Task D): from VALIDATION residuals, never same-set fit.
# ---------------------------------------------------------------------------
def dominant_cause(m):
    """Name the dominant cause from VALIDATION residuals only (never the same-set
    fit).  A cause is named only when its blocked-CV validation residual clears the
    ratio threshold in BOTH directions (front->back and back->front).  Spectral
    ripple metrics (amp/phase/group-delay) CHARACTERIZE the frequency-selective
    sub-type but do not, on their own, PROVE a cause -- the FIR (M3) must also clear.
    """
    scalar = m["scalar_only_residual"]
    if scalar < T_SCALAR_FLOOR:
        return "NO_RESIDUAL"
    cv = m["blocked_cv"]

    def clears(res3, ratio):
        # res3 = (fwd, bwd, mean); require BOTH directions below ratio*scalar
        return res3[0] < ratio * scalar and res3[1] < ratio * scalar

    # 1. boundary transient (within-frame spatial diagnostic, held-out edges)
    if m["central_training_residual"] < T_CENTRAL_RATIO * scalar \
            and m["boundary_error_ratio"] > T_BOUNDARY_RATIO:
        return "BOUNDARY_TRANSIENT"
    # 2. DC + I/Q imbalance (M2 clears in both directions)
    if clears(cv["m2"], T_DCIQ_RATIO):
        return "DC_IQ_IMBALANCE"
    # 3. pure fractional delay (M1 clears in both directions)
    if clears(cv["m1"], T_FD_RATIO):
        return "FRACTIONAL_DELAY"
    # 4. frequency-selective (short FIR M3 clears in both directions); the spectral
    #    metrics pick the amplitude-ripple vs group-delay sub-type.
    m3_sel = cv["m3"]["m3_%d" % m["fir_selected_ntap"]]
    if clears(m3_sel, T_PROVEN_RATIO):
        amp_rip = max(m["amplitude_ripple_db_pp_pos"], m["amplitude_ripple_db_pp_neg"])
        gd_rip = max(m["group_delay_ripple_samples_pos"], m["group_delay_ripple_samples_neg"])
        if amp_rip <= T_AMP_RIPPLE_DB and gd_rip > T_GROUP_DELAY_PP:
            return "GROUP_DELAY"
        if amp_rip > T_AMP_RIPPLE_DB:
            return "AMPLITUDE_PHASE_RIPPLE"
        return "FREQUENCY_SELECTIVE"
    return "NOT_IDENTIFIED"


def root_cause_result(cause):
    return "PROVEN" if cause in ("FRACTIONAL_DELAY", "DC_IQ_IMBALANCE",
                                 "AMPLITUDE_PHASE_RIPPLE", "GROUP_DELAY",
                                 "BOUNDARY_TRANSIENT", "FREQUENCY_SELECTIVE") else "NOT_PROVEN"


# ---------------------------------------------------------------------------
# Self-test: synthetic injection of each cause must be named correctly.
# ---------------------------------------------------------------------------
def _zc_ref(n=1024, amp=2048.0):
    root = 1
    k = np.arange(n, dtype=np.float64)
    ph = -math.pi * root * k * (k + 1) / n
    return (amp * np.exp(1j * ph)).astype(np.complex128)


def self_test():
    np.random.seed(20261014)
    n = 1024
    ref = _zc_ref(n)
    cases = []

    # 1. pure fractional delay 0.13 samples (circular FFT == linear for the periodic
    #    ZC preamble; a real sampling offset is band-limited, not linear-interp)
    rx = fft_delay(ref, 0.13)
    cases.append(("FRACTIONAL_DELAY", rx))

    # 2. frequency-selective amplitude ripple (2 cycles across the band)
    f = np.fft.fftfreq(n)
    H = 1.0 + 0.12 * np.cos(2.0 * math.pi * 2.0 * f)
    rx = np.fft.ifft(np.fft.fft(ref) * H)
    cases.append(("AMPLITUDE_PHASE_RIPPLE", rx))

    # 3. DC + I/Q imbalance (image at -20 dB, DC at 0.02)
    a = 1.0
    b = 0.1 * np.exp(1j * 0.7)
    c = 0.02 * rms(ref)
    rx = a * ref + b * np.conj(ref) + c
    cases.append(("DC_IQ_IMBALANCE", rx))

    # 4. boundary transient: first/last 48 samples attenuated with a ramp
    rx = ref.copy()
    edge = 48
    ramp = np.linspace(0.25, 1.0, edge)
    rx[:edge] *= ramp
    rx[-edge:] *= ramp[::-1]
    cases.append(("BOUNDARY_TRANSIENT", rx))

    # 5. group-delay ripple (pure phase non-linearity, flat magnitude, 1 cycle
    #    across the band so a 3-tap FIR stably captures it in blocked-CV)
    H = np.exp(1j * 0.08 * np.sin(2.0 * math.pi * 1.0 * f))
    rx = np.fft.ifft(np.fft.fft(ref) * H)
    cases.append(("GROUP_DELAY", rx))

    fails = 0
    for want, rx in cases:
        m = analyze_training(rx, ref)
        got = dominant_cause(m)
        ok = (got == want)
        if not ok:
            fails += 1
        print("  self-test %-24s scalar=%.4f fd=%+.3f dciq=%.4f "
              "amp_pos=%.3f ph_pos=%.2f gd_pos=%.3f central=%.4f edge=%.2f -> %s %s"
              % (want, m["scalar_only_residual"], m["fractional_delay_samples"],
                 m["dc_iq_residual"], m["amplitude_ripple_db_pp_pos"],
                 m["phase_ripple_deg_pp_pos"], m["group_delay_ripple_samples_pos"],
                 m["central_training_residual"], m["boundary_error_ratio"],
                 got, "OK" if ok else "FAIL (want %s)" % want))

    # negative control: identity channel -> NO_RESIDUAL
    m = analyze_training(ref, ref)
    got = dominant_cause(m)
    ok = (got == "NO_RESIDUAL")
    if not ok:
        fails += 1
    print("  self-test %-24s scalar=%.4f -> %s %s"
          % ("IDENTITY", m["scalar_only_residual"], got, "OK" if ok else "FAIL"))

    # negative control (bug B1 regression): complex-phase scalar channel must be
    # NO_RESIDUAL -- the OLD conj-direction bug returns residual ~= 1.3 here.
    m = analyze_training(ref * np.exp(1j * 0.7), ref)
    got = dominant_cause(m)
    ok = (got == "NO_RESIDUAL") and (m["scalar_only_residual"] < 1e-6)
    if not ok:
        fails += 1
    print("  self-test %-24s scalar=%.4f -> %s %s"
          % ("COMPLEX_PHASE_SCALAR", m["scalar_only_residual"], got,
             "OK" if ok else "FAIL (conj-direction bug leaked)"))

    return fails


def analyze_manifest(manifest_path):
    """Read the route_f_fix9r2b_waveforms.tsv and analyze every file's waveforms."""
    rows = {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        assert header[:2] == ["file_name", "kind"], "unexpected manifest header: %s" % header
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            cols = line.split("\t")
            fn, kind, path = cols[0], cols[1], cols[2]
            rows.setdefault(fn, {})[kind] = path

    results = []
    for fn in sorted(rows):
        paths = rows[fn]
        need = ("expected_training", "aligned_rx_training",
                "expected_payload", "provisional_recovered_payload")
        if not all(k in paths for k in need):
            print("  skip %s: missing kinds %s" % (fn, sorted(set(need) - set(paths))))
            continue
        tr = analyze_training(load_f32(paths["aligned_rx_training"]),
                              load_f32(paths["expected_training"]))
        pm = payload_metrics(load_f32(paths["provisional_recovered_payload"]),
                             load_f32(paths["expected_payload"]))
        eq = equivalence_gate(fn, tr)
        cause = dominant_cause(tr)
        rc = root_cause_result(cause)
        results.append({"file_name": fn, "training": tr, "payload": pm,
                        "equivalence": eq, "dominant_cause": cause,
                        "root_cause_result": rc})
        print("  %-32s scalar=%.5f corr=%.6f res=%.6f gain=%.4f@%.2fdeg fd=%+.3f "
              "dciq=%.4f m0=%.4f m1=%.4f m2=%.4f m3[%d]=%.4f central=%.4f edge=%.2f "
              "pay_corr=%.5f raw_nmse=%.4f opt_nmse=%.4f -> %s (%s) eq=%s"
              % (fn, tr["scalar_only_residual"], tr["offline_training_corr"],
                 tr["offline_training_residual"], tr["gain_mag"], tr["gain_phase_deg"],
                 tr["fractional_delay_samples"], tr["dc_iq_residual"],
                 tr["blocked_cv"]["m0"][2], tr["blocked_cv"]["m1"][2],
                 tr["blocked_cv"]["m2"][2], tr["fir_selected_ntap"],
                 tr["blocked_cv"]["m3"]["m3_%d" % tr["fir_selected_ntap"]][2],
                 tr["central_training_residual"], tr["boundary_error_ratio"],
                 pm["shape_corr"], pm["raw_nmse"], pm["optimal_scale_nmse"],
                 cause, rc, "PASS" if eq["pass"] else "FAIL"))
    return results


def cross_capture_consistency(results):
    """Cross-capture comparison (Task C): separate each capture's complex scalar g,
    then compare the COMMON normalized distortion structure (fractional delay tau,
    amplitude-ripple dB, b/a ratio) across captures.  A small spread means the
    distortion is a common channel; a large spread means a capture-specific artifact."""
    if len(results) < 2:
        return {"computed": False, "note": "fewer than 2 captures"}

    def spread(vals):
        vals = list(vals)
        return max(vals) - min(vals)

    fd = {r["file_name"]: r["training"]["fractional_delay_samples"] for r in results}
    amp = {r["file_name"]: max(r["training"]["amplitude_ripple_db_pp_pos"],
                               r["training"]["amplitude_ripple_db_pp_neg"]) for r in results}
    ba = {r["file_name"]: complex(r["training"]["b_over_a_real"],
                                  r["training"]["b_over_a_imag"]) for r in results}
    ba_vals = list(ba.values())
    ba_spread = max(abs(ba_vals[i] - ba_vals[j])
                    for i in range(len(ba_vals)) for j in range(len(ba_vals)))
    return {
        "computed": True,
        "fractional_delay_per_capture": {k: float(v) for k, v in fd.items()},
        "fractional_delay_spread": float(spread(fd.values())),
        "amplitude_ripple_db_per_capture": {k: float(v) for k, v in amp.items()},
        "amplitude_ripple_db_spread": float(spread(amp.values())),
        "b_over_a_per_capture": {k: [v.real, v.imag] for k, v in ba.items()},
        "b_over_a_spread": float(ba_spread),
    }


def main():
    ap = argparse.ArgumentParser(description="fix9r2b residual root-cause analyzer (fix9r2c)")
    ap.add_argument("--self-test", action="store_true", help="run synthetic self-test")
    ap.add_argument("--manifest", help="route_f_fix9r2b_waveforms.tsv from the board")
    ap.add_argument("--out", help="write per-file JSON results here")
    args = ap.parse_args()

    if args.self_test:
        print("analyze_fix9r2b_residuals.py --self-test")
        fails = self_test()
        print("  self-test %s" % ("PASS" if fails == 0 else "FAIL (%d)" % fails))
        return 0 if fails == 0 else 1

    if not args.manifest:
        ap.error("one of --self-test or --manifest is required")

    print("analyze_fix9r2b_residuals.py manifest=%s" % args.manifest)
    results = analyze_manifest(args.manifest)
    cross = cross_capture_consistency(results)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"per_file": results, "cross_capture": cross}, f, indent=2,
                      sort_keys=True)
        print("wrote %s" % args.out)

    # Run-level tokens
    eq_ok = all(r["equivalence"]["pass"] for r in results)
    print("FIX9R2C_ANALYZER_EQUIVALENCE result=%s" % ("PASS" if eq_ok else "FAIL"))
    if cross.get("computed"):
        print("FIX9R2C_CROSS_CAPTURE fd_spread=%.4f amp_spread=%.3f dB ba_spread=%.4f"
              % (cross["fractional_delay_spread"], cross["amplitude_ripple_db_spread"],
                 cross["b_over_a_spread"]))
    for r in results:
        print("FIX9R2C_ROOT_CAUSE file=%s cause=%s result=%s"
              % (r["file_name"], r["dominant_cause"], r["root_cause_result"]))
    print("analyzed %d file(s)" % len(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
