import numpy as np
import pytest
from scipy import signal

from dsp.fft import compute_fft
from dsp.fir import apply_fir, design_lowpass
from dsp.golden_reference import run_golden_comparison
from dsp.normalization import dc_remove, rms_normalize


def test_fft_matches_numpy_for_rectangular_window():
    rng = np.random.default_rng(4)
    iq = rng.normal(size=128) + 1j * rng.normal(size=128)
    assert np.allclose(compute_fft(iq, 128, "rectangular"), np.fft.fft(iq))


def test_fir_matches_scipy_lfilter():
    rng = np.random.default_rng(5)
    iq = rng.normal(size=512) + 1j * rng.normal(size=512)
    taps = design_lowpass(33, 12_000.0, 128_000.0)
    assert np.allclose(apply_fir(iq, taps), signal.lfilter(taps, [1.0], iq))


def test_dc_removal_and_normalization():
    rng = np.random.default_rng(6)
    iq = rng.normal(size=4096) + 1j * rng.normal(size=4096) + (2.0 - 0.4j)
    centered = dc_remove(iq)
    normalized = rms_normalize(centered, 0.5)
    assert np.mean(centered) == pytest.approx(0.0j, abs=1e-12)
    assert np.sqrt(np.mean(np.abs(normalized) ** 2)) == pytest.approx(0.5, abs=1e-12)


def test_golden_fixed_point_error_is_finite():
    rng = np.random.default_rng(8)
    iq = rng.normal(size=1024) + 1j * rng.normal(size=1024)
    report = run_golden_comparison(iq, 128_000.0)
    assert report["filtered_comparison"]["mse"] >= 0.0
    assert report["filtered_comparison"]["quantization_snr_db"] > 20.0
    assert "TODO-HARDWARE" in report["note"]

