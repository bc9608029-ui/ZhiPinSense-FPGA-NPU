"""Peak detection: resolution, merge, dynamic range, occupied bandwidth."""

import numpy as np

from src import contracts as C
from src import psd

LO_HZ = 2_400_000_000


def _tone(offset_hz: float, amplitude: float, n: int = 1024,
          sample_rate_hz: int = C.SAMPLE_RATE_HZ) -> np.ndarray:
    t = np.arange(n, dtype=np.float64) / sample_rate_hz
    return amplitude * np.exp(2j * np.pi * offset_hz * t)


def _with_noise(x: np.ndarray, sigma: float = 1e-5) -> np.ndarray:
    rng = np.random.default_rng(0)
    return x + sigma * (rng.standard_normal(x.size) + 1j * rng.standard_normal(x.size))


def test_single_tone_center_and_bin():
    iq = _with_noise(_tone(92_500.0, 1.0))
    peaks = psd.pick_peaks(LO_HZ, iq)
    assert len(peaks) == 1
    assert peaks[0].center_hz == LO_HZ + 92_500
    assert peaks[0].peak_bin == 512 + 37  # matches the FPGA fftshift 549 reference


def test_two_tones_resolvable_at_12_5_khz():
    iq = _with_noise(_tone(92_500.0, 1.0) + _tone(105_000.0, 1.0))
    peaks = psd.pick_peaks(LO_HZ, iq)
    centers = sorted(p.center_hz for p in peaks)
    assert len(peaks) == 2
    assert centers[0] == LO_HZ + 92_500
    assert centers[1] == LO_HZ + 105_000


def test_two_tones_unresolvable_at_7_5_khz_merge():
    iq = _with_noise(_tone(92_500.0, 1.0) + _tone(100_000.0, 1.0))
    peaks = psd.pick_peaks(LO_HZ, iq)
    assert len(peaks) == 1  # merged: NOT promised separable at 3 bins


def test_near_neighbor_dynamic_range_25_db_boundary():
    strong = _tone(92_500.0, 1.0)
    weak = _tone(105_000.0, 10 ** (-25.0 / 20.0))
    peaks = psd.pick_peaks(LO_HZ, _with_noise(strong + weak))
    centers = sorted(p.center_hz for p in peaks)
    assert len(peaks) == 2
    # The centroid is a power-weighted estimate; a 1-2 Hz rounding drift from
    # the strong carrier's sidelobe bias is well inside one 2500 Hz bin.
    assert abs(centers[1] - (LO_HZ + 105_000)) <= 3


def test_occupied_bandwidth_wider_signal():
    rng = np.random.default_rng(1)
    n = 1024
    # Band-limited noise ~40 kHz wide -> occupied bw around 40 kHz.
    noise = rng.standard_normal(n) + 1j * rng.standard_normal(n)
    spec = np.fft.fft(noise)
    freq = np.fft.fftfreq(n, d=1.0 / C.SAMPLE_RATE_HZ)
    mask = np.abs(freq) <= 20_000.0
    spec *= mask.astype(np.float64)
    iq = np.fft.ifft(spec)
    peaks = psd.pick_peaks(LO_HZ, iq)
    assert len(peaks) == 1
    assert peaks[0].bw_hz >= 25_000
