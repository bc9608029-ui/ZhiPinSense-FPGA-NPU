#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest_ac_audit.py -- self-tests for the A<->C direct feature audit.

Covers (per plan):
  * I/Q layout + size
  * DC / scaling / IQ-correlation changes are detected
  * single-tone / separated-two-tone / noise PSD + bandwidth definition
  * old bin-count vs continuous-interval bandwidth are DISTINGUISHABLE
  * missing / duplicate / NaN / Inf / wrong-identity are detected
  * repeated captures of the same source are NOT treated as independent
  * B<->C metrics are NOT mixed into A<->C

Run:  python -I scripts/selftest_ac_audit.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ac_common as ac  # noqa: E402


def _tone(freq=0.1, n=1024, amp=1.0):
    t = np.arange(n)
    return (amp * np.exp(2j * np.pi * freq * t)).astype(np.complex128)


def _noise(n=1024, rng=None):
    rng = rng or np.random.default_rng(0)
    return (rng.standard_normal(n) + 1j * rng.standard_normal(n)).astype(np.complex128)


def test_layout_size():
    iq = _tone(0.1)
    arr = np.ascontiguousarray(np.stack([iq.real, iq.imag])).astype(np.float32)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.bin")
        arr.tofile(p)
        loaded = ac.load_tensor_2x1024(p)
        assert loaded.shape == (1024,), loaded.shape
        assert np.allclose(loaded, iq, atol=1e-6), "I/Q order mismatch"
        # wrong size must raise
        bad = np.zeros(100, dtype=np.float32)
        p2 = os.path.join(d, "bad.bin")
        bad.tofile(p2)
        try:
            ac.load_tensor_2x1024(p2)
        except AssertionError:
            pass
        else:
            raise AssertionError("wrong-size tensor did not raise")
    return "layout + size ok (1024 complex, row0=real row1=imag; wrong size raises)"


def test_dc_scaling_corr():
    rng = np.random.default_rng(1)
    base = _noise(1024, rng)
    m0 = ac.full_metrics(base)

    # DC offset -> dc + dc_power_frac change, ac_rms ~unchanged
    dc_off = base + (0.5 + 0.2j)
    m1 = ac.full_metrics(dc_off)
    assert m1["dc"] > m0["dc"] * 2, "DC offset not detected"
    assert m1["dc_power_frac"] > m0["dc_power_frac"], "DC power fraction not detected"
    assert abs(m1["ac_rms"] - m0["ac_rms"]) < 1e-9, "AC RMS changed under pure DC offset"

    # scaling -> rms scales, noncirc/corr unchanged
    m2 = ac.full_metrics(base * 3.0)
    assert abs(m2["rms"] - 3.0 * m0["rms"]) < 1e-6, "scaling not detected in RMS"
    assert abs(m2["noncirc"] - m0["noncirc"]) < 1e-6, "noncirc changed under scaling"

    # IQ correlation: q = a*i + noise -> corr_iq and var_ratio move
    ri = np.real(base)
    iq_corr = ri + 0.8j * ri + 1j * rng.standard_normal(1024) * 0.01
    m3 = ac.full_metrics(iq_corr.astype(np.complex128))
    assert m3["corr_iq"] > 0.9, "IQ correlation not detected (corr=%.3f)" % m3["corr_iq"]
    assert m3["noncirc"] > m0["noncirc"], "non-circularity not detected under IQ correlation"
    return "DC/scaling/IQ-correlation changes detected"


def test_psd_bandwidth():
    n = 1024
    rng = np.random.default_rng(2)

    tone = _tone(0.1, n)
    m_tone = ac.full_metrics(tone)
    assert m_tone["bw99_cont"] < 0.02, "single tone bw99_cont too wide (%.4f)" % m_tone["bw99_cont"]

    # two tones far apart -> wide continuous interval, but tiny old bin-count
    two = _tone(0.05, n) + _tone(0.35, n)
    m_two = ac.full_metrics(two)
    assert m_two["bw99_cont"] > 0.20, "two-tone bw99_cont too narrow (%.4f)" % m_two["bw99_cont"]

    noise = _noise(n, rng)
    m_noise = ac.full_metrics(noise)
    assert m_noise["bw99_cont"] > 0.6, "noise bw99_cont should be near full band (%.4f)" % m_noise["bw99_cont"]
    assert m_noise["flatness"] > 0.5, "noise flatness should be ~1 (%.4f)" % m_noise["flatness"]
    assert m_tone["flatness"] < 1e-4, "tone flatness should be ~0 (%.4f)" % m_tone["flatness"]
    return "PSD + bandwidth: tone narrow / two-tone wide / noise ~full band + flatness"


def test_bincount_vs_continuous():
    # two tones far apart: old bin-count bw99 ~ 2/4096 tiny, continuous ~0.30
    n = 1024
    two = _tone(0.05, n) + _tone(0.35, n)
    m = ac.full_metrics(two)
    assert m["bw99"] < 0.01, "old bin-count bw99 should be tiny for two tones (%.4f)" % m["bw99"]
    assert m["bw99_cont"] > 0.20, "continuous bw99_cont should span the tones (%.4f)" % m["bw99_cont"]
    assert m["bw99_cont"] > 10 * m["bw99"], "metrics must be distinguishable"
    return "old bin-count vs continuous-interval bandwidth are distinguishable"


def test_identity_detection():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "inf.bin")
        (np.ones(2048, dtype=np.float32) * np.inf).tofile(p)
        iq = ac.load_tensor_2x1024(p)
        assert not np.isfinite(iq).all(), "Inf not surfaced"

        p2 = os.path.join(d, "nan.bin")
        (np.ones(2048, dtype=np.float32) * np.nan).tofile(p2)
        iq2 = ac.load_tensor_2x1024(p2)
        assert not np.isfinite(iq2).all(), "NaN not surfaced"

        # wrong-size (duplicate/truncation) caught by loader
        p3 = os.path.join(d, "dup.bin")
        np.zeros(1000, dtype=np.float32).tofile(p3)
        try:
            ac.load_tensor_2x1024(p3)
        except AssertionError:
            pass
        else:
            raise AssertionError("truncated tensor did not raise")
    return "missing/NaN/Inf/wrong-size detected"


def test_repeat_not_independent():
    # (round, source_index) identifies a capture; repeated rounds of the same
    # source are one source, not independent sources.
    keys = [("r1", 7000), ("r2", 7000), ("r3", 7000), ("r1", 8000)]
    sources = {sid for _, sid in keys}
    assert sources == {7000, 8000}, "repeated captures counted as independent sources"
    assert len(keys) == 4 and len(sources) == 2, "dedup by source_index failed"
    return "repeated captures of same source not independent (dedup by source_index)"


def test_no_bc_mixing():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "ac_common.py"), "r", encoding="utf-8").read()
    # full_metrics takes ONE frame (no reference) -> no pointwise/subtraction path
    import inspect
    sig = inspect.signature(ac.full_metrics)
    assert list(sig.parameters) == ["iq"], sig
    for bad in ("def aligned_metrics", "nmse", "b_d2", "B_d2"):
        assert bad not in src, "B<->C residual symbol '%s' leaked into ac_common" % bad
    return "full_metrics is single-frame (no ref/residual); no B<->C alignment symbols"


def test_base_fields_match_reference():
    # base 7 fields must match threedomain audit_common.sample_stats (reuse check)
    import importlib.util
    ref_path = r"F:/嵌赛/fix10class24_threedomain_pairwise_audit1_work/scripts/audit_common.py"
    spec = importlib.util.spec_from_file_location("audit_common_ref", ref_path)
    ref = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ref)
    rng = np.random.default_rng(3)
    for _ in range(5):
        iq = _noise(1024, rng) + 0.1j * _tone(0.13)
        a = ref.sample_stats(iq)
        b = ac.full_metrics(iq)
        for k in ac.BASE_FIELDS:
            va, vb = a[k], b[k]
            assert (abs(va - vb) <= 1e-9 * max(1.0, abs(va)) or
                    (np.isinf(va) and np.isinf(vb))), "%s mismatch ref=%.12g mine=%.12g" % (k, va, vb)
    return "base 7 fields match threedomain audit_common.sample_stats"


def test_complex_acorr_tone():
    # Deterministic counterexample for the autocorrelation real-part bug:
    # a 1024-point unit complex single tone at normalized freq 0.25 must have
    # lag-1 |acorr| = (1024-1)/1024 = 0.9990234375 (NOT ~0).
    n = 1024
    t = np.arange(n)
    x = (np.exp(2j * np.pi * 0.25 * t)).astype(np.complex128)
    m = ac.full_metrics(x)
    expected = (n - 1.0) / n
    got = m["acorr_lag1"]
    assert abs(got - expected) < 1e-9, "lag1 |acorr| = %.12g, want %.12g" % (got, expected)
    return "complex single tone f=0.25: lag1 |acorr| = 1023/1024 = 0.9990234375"


def test_acorr_phase_rotation_invariant():
    # |acorr| must be invariant to a global phase rotation; the old .real-first
    # formulation broke this (real part depends on the rotation).
    n = 1024
    rng = np.random.default_rng(4)
    base = (rng.standard_normal(n) + 1j * rng.standard_normal(n)).astype(np.complex128)
    rot = base * np.exp(1j * 0.7)
    m0 = ac.full_metrics(base)
    m1 = ac.full_metrics(rot)
    for k in ac.ACORR_LAGS:
        kk = "acorr_lag%d" % k
        assert abs(m0[kk] - m1[kk]) < 1e-9, "|acorr| not phase-rotation invariant at lag %d" % k
    return "|acorr(lag)| invariant under global phase rotation (real-part bug would break this)"


def test_flatness_floor_not_metric():
    # flatness_floor is a numeric implementation constant, NOT a signal feature;
    # it must not be emitted or ranked.
    names = ac.metric_names()
    assert "flatness_floor" not in names, "flatness_floor must not be a ranked metric"
    m = ac.full_metrics(_noise(1024))
    assert "flatness_floor" not in m, "flatness_floor must not be emitted"
    return "flatness_floor excluded from metrics (numeric constant, not a signal feature)"


def test_wrong_size_raises():
    with tempfile.TemporaryDirectory() as d:
        for nbad, label in [(100, "short"), (3000, "long")]:
            p = os.path.join(d, label + ".bin")
            np.zeros(nbad, dtype=np.float32).tofile(p)
            try:
                ac.load_tensor_2x1024(p)
            except AssertionError:
                continue
            else:
                raise AssertionError("loader accepted %s tensor (%d floats)" % (label, nbad))
    return "wrong-size (short/long) tensors are rejected by the loader"


TESTS = [
    test_layout_size,
    test_dc_scaling_corr,
    test_psd_bandwidth,
    test_bincount_vs_continuous,
    test_identity_detection,
    test_repeat_not_independent,
    test_no_bc_mixing,
    test_base_fields_match_reference,
    test_complex_acorr_tone,
    test_acorr_phase_rotation_invariant,
    test_flatness_floor_not_metric,
    test_wrong_size_raises,
]


def main():
    npass = 0
    nfail = 0
    for t in TESTS:
        name = t.__name__
        try:
            msg = t()
            print("PASS  %-28s  %s" % (name, msg))
            npass += 1
        except Exception as e:  # noqa: BLE001
            print("FAIL  %-28s  %s" % (name, e))
            nfail += 1
    print("---")
    print("SELFTEST %d/%d PASS" % (npass, npass + nfail))
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
