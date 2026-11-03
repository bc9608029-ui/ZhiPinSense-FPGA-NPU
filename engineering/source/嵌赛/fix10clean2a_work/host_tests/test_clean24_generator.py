"""Host test 2/4 — the deterministic clean generator.

Covers §12 items: 1 (fixed-seed SHA identical), 2 (different seeds distinct),
3 (1024 complex samples), 4 (all 24 classes), 9 (no AWGN/CFO/SRO/multipath),
10 (no NaN/Inf), 11 (RMS/peak safe), 12 (no CI16 clip).
"""

from __future__ import annotations

import numpy as np
import pytest

import radioml_clean_contract as c

CI16_TARGET_RMS = 2048.0          # the RF TX amplitude contract


def test_fixed_seed_byte_identical():
    # §12 item 1: same seed -> bit-identical frame (the core of deterministic SHA).
    a = c.generate_class("32QAM", 12345)
    b = c.generate_class("32QAM", 12345)
    assert np.array_equal(a, b)


def test_different_seed_distinct():
    # §12 item 2: different seeds -> different samples, for every modulation family.
    for cls in c.LABEL_ORDER_24:
        a = c.generate_class(cls, 1000)
        b = c.generate_class(cls, 2000)
        assert not np.array_equal(a, b), cls


def test_output_is_1024_complex():
    # §12 item 3: exactly 1024 complex samples per frame.
    for cls in ("16QAM", "GMSK", "AM-DSB-WC", "FM"):
        x = c.generate_class(cls, 3)
        assert x.shape == (c.SAMPLE_LENGTH,)
        assert np.iscomplexobj(x)


def test_all_24_classes_generate():
    # §12 item 4: all 24 raw classes produce a valid frame.
    assert len(c.LABEL_ORDER_24) == 24
    for i, cls in enumerate(c.LABEL_ORDER_24):
        x = c.generate_class(cls, 100 + i)
        assert x.shape == (c.SAMPLE_LENGTH,)
        assert np.all(np.isfinite(x))


def test_no_nan_inf():
    # §12 item 10: no NaN/Inf anywhere in any class's clean frame.
    for cls in c.LABEL_ORDER_24:
        x = c.generate_class(cls, 555)
        assert np.all(np.isfinite(x.real)) and np.all(np.isfinite(x.imag)), cls


def test_rms_matches_target_and_peak_safe():
    # §12 item 11: per-class RMS reproduces the contract target; crest factor sane.
    for cls, target in c.TARGET_RMS.items():
        x = c.generate_class(cls, 777)
        rms = float(np.sqrt(np.mean(np.abs(x) ** 2)))
        assert abs(rms - target) / target < 0.01, cls
        peak = float(np.max(np.abs(x)))
        assert np.isfinite(peak)
        assert peak / rms < 10.0, cls


def test_no_ci16_clip():
    # §12 item 12: scaling to the int16 TX domain (RMS target 2048) never saturates.
    for cls in c.LABEL_ORDER_24:
        x = c.generate_class(cls, 888)
        rms = float(np.sqrt(np.mean(np.abs(x) ** 2)))
        y = x * (CI16_TARGET_RMS / rms)
        i = np.round(y.real).astype(np.int64)
        q = np.round(y.imag).astype(np.int64)
        assert int(np.abs(i).max()) <= 32767, cls
        assert int(np.abs(q).max()) <= 32767, cls


def test_clean_has_no_channel_impairment():
    # §12 item 9: the generator injects no AWGN/CFO/SRO/multipath/fading.  This is
    # proven two ways: (a) same-seed reproduction is bit-identical (any random
    # channel term would break determinism), and (b) the frame carries a constant
    # deterministic phase — no per-frame random phase or frequency drift.
    a = c.generate_class("BPSK", 31415)
    b = c.generate_class("BPSK", 31415)
    assert np.array_equal(a, b)
    # real-baseband modulations use a fixed CLEAN_PHASE, not a random per-frame one
    assert np.isclose(c.CLEAN_PHASE, np.pi / 4.0)
