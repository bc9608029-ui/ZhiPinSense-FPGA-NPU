from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest
from scipy import signal

from dsp.wideband_discovery import DiscoveryConfig, discover_signals
from hardware.fpga.python.wideband_reference import ExtractionRequest, extract_candidate


SAMPLE_RATE = 1_024_000.0
RECORD_LENGTH = 65_536
DETECTION_CONFIG = DiscoveryConfig(
    fft_length=2048,
    hop_length=1024,
    threshold_db=7.0,
    merge_gap_bins=2,
    min_region_bins=2,
)


def _complex_noise(rng: np.random.Generator, length: int) -> np.ndarray:
    return (rng.normal(size=length) + 1j * rng.normal(size=length)) / np.sqrt(2.0)


def _tone_record(frequency_hz: float, snr_db: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    sample_index = np.arange(RECORD_LENGTH)
    tone = np.exp(1j * 2.0 * np.pi * frequency_hz * sample_index / SAMPLE_RATE)
    noise = _complex_noise(rng, RECORD_LENGTH) * 10.0 ** (-snr_db / 20.0)
    return tone + noise


def _bandlimited_record(
    center_hz: float,
    bandwidth_hz: float,
    snr_db: float,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    taps = signal.firwin(257, 0.42 * bandwidth_hz, fs=SAMPLE_RATE)
    baseband = signal.lfilter(taps, [1.0], _complex_noise(rng, RECORD_LENGTH))
    baseband /= np.sqrt(np.mean(np.abs(baseband[512:]) ** 2))
    sample_index = np.arange(RECORD_LENGTH)
    shifted = baseband * np.exp(1j * 2.0 * np.pi * center_hz * sample_index / SAMPLE_RATE)
    noise = _complex_noise(rng, RECORD_LENGTH)
    noise *= np.sqrt(np.mean(np.abs(shifted) ** 2) / np.mean(np.abs(noise) ** 2))
    noise *= 10.0 ** (-snr_db / 20.0)
    return shifted + noise


@pytest.mark.parametrize("snr_db", [-15.0, -8.0, 0.0, 10.0])
def test_single_signal_detected_across_snr(snr_db: float) -> None:
    frequency_hz = -173_000.0
    result = discover_signals(_tone_record(frequency_hz, snr_db, 500), SAMPLE_RATE, DETECTION_CONFIG)
    assert len(result["detections"]) == 1
    detection = result["detections"][0]
    assert abs(detection["center_frequency_hz"] - frequency_hz) <= result["bin_width_hz"]
    assert detection["estimated_snr_db"] > 0.0


def test_detector_snr_estimate_is_monotonic_not_absolute_calibration() -> None:
    estimates = []
    for snr_db in (-15.0, -8.0, 0.0, 10.0):
        result = discover_signals(_tone_record(-173_000.0, snr_db, 501), SAMPLE_RATE, DETECTION_CONFIG)
        estimates.append(result["detections"][0]["estimated_snr_db"])
    assert all(first < second for first, second in pairwise(estimates))


@pytest.mark.parametrize("frequency_hz", [-310_000.0, -120_000.0, 75_000.0, 300_000.0])
def test_frequency_offset_estimation(frequency_hz: float) -> None:
    result = discover_signals(_tone_record(frequency_hz, 0.0, 600), SAMPLE_RATE, DETECTION_CONFIG)
    assert len(result["detections"]) == 1
    assert abs(result["detections"][0]["center_frequency_hz"] - frequency_hz) <= result["bin_width_hz"]


def test_two_signals_are_separated() -> None:
    first = _tone_record(-210_000.0, 3.0, 700)
    # Reuse only the deterministic tone from the second record; keep one noise realization.
    sample_index = np.arange(RECORD_LENGTH)
    second_tone = 0.7 * np.exp(1j * 2.0 * np.pi * 135_000.0 * sample_index / SAMPLE_RATE)
    result = discover_signals(first + second_tone, SAMPLE_RATE, DETECTION_CONFIG)
    centers = sorted(item["center_frequency_hz"] for item in result["detections"])
    assert len(centers) == 2
    assert abs(centers[0] + 210_000.0) <= result["bin_width_hz"]
    assert abs(centers[1] - 135_000.0) <= result["bin_width_hz"]


def test_occupied_bandwidth_tracks_injected_bandwidth() -> None:
    injected = (24_000.0, 48_000.0, 96_000.0)
    estimated = []
    config = DiscoveryConfig(fft_length=2048, hop_length=1024, threshold_db=5.0, merge_gap_bins=8, min_region_bins=3)
    for index, bandwidth_hz in enumerate(injected):
        record = _bandlimited_record(130_000.0, bandwidth_hz, 10.0, 800 + index)
        result = discover_signals(record, SAMPLE_RATE, config)
        assert len(result["detections"]) == 1
        detection = result["detections"][0]
        assert abs(detection["center_frequency_hz"] - 130_000.0) < 3 * result["bin_width_hz"]
        assert 0.55 * bandwidth_hz <= detection["occupied_bandwidth_hz"] <= 1.45 * bandwidth_hz
        estimated.append(detection["occupied_bandwidth_hz"])
    assert estimated[0] < estimated[1] < estimated[2]


@pytest.mark.parametrize("frequency_hz", [-240_000.0, 90_000.0, 260_000.0])
def test_ddc_recenters_and_resamples_to_amr_contract(frequency_hz: float) -> None:
    record = _tone_record(frequency_hz, 20.0, 900)
    request = ExtractionRequest(
        candidate_id=4,
        center_frequency_hz=frequency_hz,
        occupied_bandwidth_hz=32_000.0,
    )
    frame, metadata = extract_candidate(record, SAMPLE_RATE, request)
    phase_increment = np.angle(frame[1:] * np.conj(frame[:-1]))
    assert frame.shape == (1024,)
    assert frame.dtype == np.complex64
    assert np.isfinite(frame).all()
    assert abs(float(np.mean(phase_increment))) < 0.01
    assert metadata["target_sample_rate_hz"] == 128_000.0
    assert metadata["resample_up"] == 1
    assert metadata["resample_down"] == 8
    assert metadata["symbol_rate_status"] == "TODO-SYMBOL-RATE"


def test_invalid_wideband_contract_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        DiscoveryConfig(fft_length=1024, hop_length=0)
    with pytest.raises(ValueError):
        discover_signals(np.ones(2048, dtype=np.complex64), 0.0)
