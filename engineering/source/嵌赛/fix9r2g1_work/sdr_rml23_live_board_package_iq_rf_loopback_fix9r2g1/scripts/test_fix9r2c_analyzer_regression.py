#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_fix9r2c_analyzer_regression.py -- 16-item regression for the fix9r2c analyzer
(scripts/analyze_fix9r2b_residuals.py).  stdlib + numpy only; independent of the
board (no waveform files needed).  Run with:

    python -I scripts/test_fix9r2c_analyzer_regression.py

The 16 items pin the three complex-math bug fixes (A1 scalar direction, A2 float()
ComplexWarning guardrail, A3 two-sideband no-cross-DC group delay) plus the Task C
blocked-CV / FIR tap-set and Task B equivalence-gate logic.

Two MANDATORY guards (task book Task E):
  (1) a complex-phase scalar channel rx = exp(j*0.7)*ref MUST be NO_RESIDUAL with
      scalar residual ~ 0 (the old conj-direction bug returns ~ 1.3).
  (2) under the targeted warning upgrade, the OLD float(np.vdot(x, p)) MUST raise
      numpy ComplexWarning (the guardrail that catches bug A2).
"""

import math
import os
import sys
import warnings

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_fix9r2b_residuals as A   # noqa: E402


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


# ---- deterministic helpers -------------------------------------------------
def zc(n=1024, amp=2048.0):
    return A._zc_ref(n, amp)


def apply_fir(ref, h):
    """Linear-convolution centered FIR (mirrors A._fir_design), returns rx = h * ref."""
    ntap = len(h)
    half = ntap // 2
    n = ref.size
    out = np.zeros(n, dtype=np.complex128)
    for j in range(ntap):
        shift = half - j
        lo = max(0, -shift)
        hi = min(n, n - shift)
        if hi > lo:
            out[lo:hi] += h[j] * ref[lo + shift:hi + shift]
    return out


def _boundary(ref):
    """First/last 48 samples ramped (the self-test BOUNDARY_TRANSIENT injection)."""
    rx = ref.copy()
    edge = 48
    ramp = np.linspace(0.25, 1.0, edge)
    rx[:edge] *= ramp
    rx[-edge:] *= ramp[::-1]
    return rx


# ---- 1. scalar fit forward-gain direction (bug A1) -------------------------
@test
def test_scalar_fit_forward_gain_direction():
    ref = zc()
    g = 0.02 * np.exp(1j * 0.7)
    rx = g * ref
    gest, res, _ = A.scalar_fit(rx, ref)
    assert abs(gest - g) / abs(g) < 1e-9, (gest, g)
    assert res < 1e-9, res


# ---- 2. MANDATORY (1): complex-phase scalar channel -> NO_RESIDUAL ---------
@test
def test_complex_phase_scalar_channel_no_residual():
    ref = zc()
    m = A.analyze_training(ref * np.exp(1j * 0.7), ref)
    cause = A.dominant_cause(m)
    assert cause == "NO_RESIDUAL", cause
    assert m["scalar_only_residual"] < 1e-6, m["scalar_only_residual"]


# ---- 3. MANDATORY (2): old float(np.vdot(x,p)) raises ComplexWarning -------
@test
def test_old_float_vdot_raises_complexwarning():
    x = np.array([1 + 2j, 3 - 1j], dtype=np.complex128)
    p = np.array([2 - 1j, 1 + 1j], dtype=np.complex128)
    v = np.vdot(x, p)
    assert abs(v.imag) > 1e-12, v          # must actually be complex
    cw = A._COMPLEX_WARNING
    assert cw is not None
    raised = False
    with warnings.catch_warnings():
        warnings.simplefilter("error", category=cw)
        try:
            float(v)
        except cw:
            raised = True
    assert raised, "float(np.vdot(x,p)) did not raise ComplexWarning"


# ---- 4. payload_metrics corr is magnitude-only (bug A2) --------------------
@test
def test_payload_metrics_phase_invariant_shape_corr():
    p = zc(4096, 1000.0)
    rec = p * np.exp(1j * 0.7)
    pm = A.payload_metrics(rec, p)
    assert abs(pm["shape_corr"] - 1.0) < 1e-6, pm["shape_corr"]
    # the old float() bug would collapse corr to |cos(0.7)| ~ 0.765
    assert abs(pm["shape_corr"] - abs(math.cos(0.7))) > 0.1


# ---- 5. nmse split: raw vs optimal-scale (Task I) --------------------------
@test
def test_payload_metrics_nmse_split():
    p = zc(4096, 1000.0)
    rec = 2.5 * p                      # recovered is 2.5x too large (pure gain error)
    pm = A.payload_metrics(rec, p)
    assert pm["optimal_scale_nmse"] < 1e-9, pm["optimal_scale_nmse"]
    assert pm["raw_nmse"] > 0.1, pm["raw_nmse"]
    # g* = vdot(x,p)/vdot(x,x) = 1/2.5 = 0.4 (scale recovered DOWN to match expected)
    assert abs(pm["gain_ratio"] - 0.4) < 1e-9, pm["gain_ratio"]
    assert abs(pm["gain_error_db"] - 20.0 * math.log10(0.4)) < 1e-6, pm["gain_error_db"]


# ---- 6. two-sideband group delay: no cross-DC artifact (bug A3) ------------
@test
def test_band_response_no_cross_dc_artifact():
    ref = zc()
    g, _, _ = A.scalar_fit(ref, ref)
    band = A.band_response(ref, ref, g)   # identity channel: H == 1
    for tag in ("pos", "neg"):
        assert band[tag]["amp_pp_db"] < 0.1, band[tag]
        assert band[tag]["phase_pp_deg"] < 0.5, band[tag]
        assert band[tag]["gd_pp_samples"] < 0.5, band[tag]  # no spurious ~62


# ---- 7. pos/neg masks are contiguous and never cross DC --------------------
@test
def test_pos_neg_masks_disjoint_no_dc():
    n = 1024
    pm = A._pos_mask(n)
    nm = A._neg_mask(n)
    f = np.fft.fftfreq(n)
    assert not np.any(pm & nm), "masks overlap"
    assert np.all(f[pm] > 0.0) and np.all(f[nm] < 0.0)
    assert np.all(np.abs(f[pm]) >= A.BAND_LO) and np.all(np.abs(f[pm]) <= A.BAND_HI)
    assert np.all(np.abs(f[nm]) >= A.BAND_LO) and np.all(np.abs(f[nm]) <= A.BAND_HI)
    assert not pm[np.argmin(np.abs(f))] and not nm[np.argmin(np.abs(f))]


# ---- 8. fractional-delay estimate recovers the injected tau ----------------
@test
def test_fractional_delay_estimate_recovery():
    ref = zc()
    rx = A.fft_delay(ref, 0.13)
    tp, tn, ta, res = A.fractional_delay_estimate(rx, ref)
    assert abs(ta - 0.13) < 0.01, (tp, tn, ta)
    _, scalar_res, _ = A.scalar_fit(rx, ref)
    assert res < scalar_res, (res, scalar_res)


# ---- 9. M1 (scalar + fractional delay) beats M0 (scalar) -------------------
@test
def test_m1_reduces_fractional_delay():
    ref = zc()
    rx = A.fft_delay(ref, 0.13)
    cv = A.model_table(rx, ref)
    assert cv["m1"][2] < cv["m0"][2], (cv["m0"], cv["m1"])


# ---- 10. M3 FIR generalizes to the held-out segment (stationary channel) ---
@test
def test_m3_fir_generalizes_stationary_channel():
    ref = zc()
    h = np.array([0.2, -0.3j, 1.0, 0.3j, 0.2], dtype=np.complex128)
    rx = apply_fir(ref, h)
    cv = A.model_table(rx, ref)
    # a correct 5-tap model must generalize across the blocked-CV validation
    # segment; a scalar cannot capture the frequency selectivity.
    assert cv["m3"]["m3_5"][2] < 0.3 * cv["m0"][2], (cv["m0"], cv["m3"]["m3_5"])


# ---- 11. blocked-CV geometry: guard respected, est/val disjoint ------------
@test
def test_blocked_cv_geometry_disjoint_guard():
    n = 1024
    assert A.CV_GUARD >= 5                    # >= FIR half length (max tap 11 -> 5)
    assert A.CV_MID + A.CV_GUARD < n
    assert A.CV_MID - A.CV_GUARD > 0
    # forward est [0,CV_MID) vs val [CV_MID+guard, n): no overlap
    assert A.CV_MID + A.CV_GUARD > A.CV_MID


# ---- 12. M3 tap set {3,5,7,9,11} fully covered -----------------------------
@test
def test_m3_tap_set_full_coverage():
    ref = zc()
    rx = A.fft_delay(ref, 0.05)
    cv = A.model_table(rx, ref)
    for nt in A.FIR_TAPS:
        assert "m3_%d" % nt in cv["m3"], nt
        assert len(cv["m3"]["m3_%d" % nt]) == 3, nt
    m = A.analyze_training(rx, ref)
    assert m["fir_selected_ntap"] in A.FIR_TAPS
    assert m["fir_best_ntap"] in A.FIR_TAPS


# ---- 13. tap selection prefers the shortest clearing tap -------------------
@test
def test_tap_selection_shortest_clearing():
    ref = zc()
    h = np.array([0.4j, 1.0, 0.4j], dtype=np.complex128)   # 3-tap channel
    rx = apply_fir(ref, h)
    m = A.analyze_training(rx, ref)
    assert m["fir_selected_ntap"] == 3, m["fir_selected_ntap"]


# ---- 14. equivalence gate: 4 asserts (2 files x corr/res) ------------------
@test
def test_equivalence_gate_4_asserts():
    m6 = {"offline_training_corr": 0.972983, "offline_training_residual": 0.237286}
    m2 = {"offline_training_corr": 0.976160, "offline_training_residual": 0.222355}
    e6 = A.equivalence_gate("quantized_d2_2p56m_000006.ci16", m6)
    e2 = A.equivalence_gate("quantized_d2_2p56m_000002.ci16", m2)
    assert e6["pass"], e6                 # corr/res 000006
    assert e2["pass"], e2                 # corr/res 000002
    bad = A.equivalence_gate("quantized_d2_2p56m_000006.ci16",
                             {"offline_training_corr": 0.9,
                              "offline_training_residual": 0.3})
    assert not bad["pass"], bad           # perturbed -> FAIL
    unk = A.equivalence_gate("nope.ci16", m6)
    assert not unk["checked"] and not unk["pass"], unk   # unknown -> not checked


# ---- 15. the five synthetic cause injections are named correctly -----------
@test
def test_self_test_five_causes():
    n = 1024
    ref = zc()
    f = np.fft.fftfreq(n)
    cases = [
        ("FRACTIONAL_DELAY", A.fft_delay(ref, 0.13)),
        ("AMPLITUDE_PHASE_RIPPLE",
         np.fft.ifft(np.fft.fft(ref) * (1.0 + 0.12 * np.cos(2.0 * math.pi * 2.0 * f)))),
        ("DC_IQ_IMBALANCE",
         1.0 * ref + 0.1 * np.exp(1j * 0.7) * np.conj(ref) + 0.02 * A.rms(ref)),
        ("BOUNDARY_TRANSIENT", _boundary(ref)),
        ("GROUP_DELAY",
         np.fft.ifft(np.fft.fft(ref) * np.exp(1j * 0.08 * np.sin(2.0 * math.pi * 1.0 * f)))),
    ]
    for want, rx in cases:
        m = A.analyze_training(rx, ref)
        got = A.dominant_cause(m)
        assert got == want, (want, got)


# ---- 16. identity negative control -> NO_RESIDUAL --------------------------
@test
def test_self_test_identity_negative_control():
    ref = zc()
    m = A.analyze_training(ref, ref)
    assert A.dominant_cause(m) == "NO_RESIDUAL", A.dominant_cause(m)
    assert m["scalar_only_residual"] < 1e-6, m["scalar_only_residual"]


def main():
    fails = []
    for fn in TESTS:
        name = fn.__name__
        try:
            fn()
            print("PASS %s" % name)
        except AssertionError as e:
            fails.append((name, str(e)))
            print("FAIL %s: %s" % (name, e))
        except Exception as e:                      # noqa: BLE001
            fails.append((name, repr(e)))
            print("ERROR %s: %r" % (name, e))
    n = len(TESTS)
    passed = n - len(fails)
    print("%d/%d PASS" % (passed, n))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
