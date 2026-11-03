"""OOD generator tests: shape, RMS, determinism, and three-way isolation."""
import numpy as np
import pytest

from datasets import m25b_ood_generator as g


def test_family_shape_and_dtype():
    arr, meta = g.generate_family("LFM", count=8, split_code=0, seed=2026)
    assert arr.shape == (8, 2, 1024)
    assert arr.dtype == np.float32
    assert meta["modulation"] == "LFM"
    assert meta["source"] == "far"


def test_rms_is_one():
    arr, _ = g.generate_family("CW", count=16, split_code=1, seed=2026)
    rms = np.sqrt(np.mean(arr[:, 0, :] ** 2 + arr[:, 1, :] ** 2, axis=1))
    assert np.allclose(rms, 1.0, atol=1e-3)


def test_deterministic_same_seed_split():
    a, _ = g.generate_family("2FSK", count=4, split_code=0, seed=2026)
    b, _ = g.generate_family("2FSK", count=4, split_code=0, seed=2026)
    assert np.array_equal(a, b)


def test_three_way_isolation():
    a, _ = g.generate_family("LFM", count=4, split_code=0, seed=2026)
    b, _ = g.generate_family("LFM", count=4, split_code=1, seed=2026)
    c, _ = g.generate_family("LFM", count=4, split_code=2, seed=2026)
    assert not np.array_equal(a, b)
    assert not np.array_equal(a, c)
    assert not np.array_equal(b, c)


def test_source_mapping():
    assert g.source_of("2FSK") == "near"
    assert g.source_of("GFSK") == "near"
    assert g.source_of("OFDM") == "near"
    assert g.source_of("AM-DSB") == "ambiguous"
    assert g.source_of("WBFM") == "ambiguous"
    assert g.source_of("LFM") == "far"
    assert g.source_of("CW") == "far"


def test_invalid_modulation_raises():
    with pytest.raises(ValueError):
        g.generate_family("NOT_A_MOD", count=2, split_code=0)
    with pytest.raises(ValueError):
        g.generate_family("LFM", count=2, split_code=99)


def test_single_ood_iq_complex():
    iq, meta = g.generate_ood_iq("LFM")
    assert iq.dtype == np.complex64
    assert iq.shape == (1024,)
    assert meta["ood_synthesis"] == "synthetic"
