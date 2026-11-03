import numpy as np
import pytest

from datasets.modulation_generator import _fsk_from_symbols, constellation_points, generate_iq


SIGNAL_CONFIG = {
    "sample_rate": 128_000.0,
    "symbol_rate": 16_000.0,
    "samples_per_symbol": 8,
    "sample_length": 1024,
    "amplitude": 1.0,
    "frequency_offset": 0.0,
    "phase_offset": 0.0,
    "pulse_shape": {"rolloff": 0.35, "span_symbols": 8},
    "ofdm": {"fft_length": 256, "cyclic_prefix": 64, "active_subcarriers": 48},
    "modulations": ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"],
}


@pytest.mark.parametrize("name,count", [("BPSK", 2), ("QPSK", 4), ("8PSK", 8), ("16QAM", 16), ("64QAM", 64)])
def test_constellation_cardinality_and_power(name, count):
    points = constellation_points(name)
    assert len(np.unique(points)) == count
    assert np.mean(np.abs(points) ** 2) == pytest.approx(1.0, abs=1e-12)


def test_qpsk_quadrants_are_balanced():
    points = constellation_points("QPSK")
    assert set(np.sign(points.real)) == {-1.0, 1.0}
    assert set(np.sign(points.imag)) == {-1.0, 1.0}


def test_fsk_frequency_and_continuous_phase():
    sample_rate = 128_000.0
    separation = 16_000.0
    iq = _fsk_from_symbols(np.ones(100), 8, sample_rate, separation)
    phase = np.unwrap(np.angle(iq))
    estimated_hz = np.mean(np.diff(phase)) * sample_rate / (2.0 * np.pi)
    assert estimated_hz == pytest.approx(separation / 2.0, rel=1e-6)
    assert np.max(np.abs(np.diff(phase, n=2))) < 1e-10


@pytest.mark.parametrize("name", SIGNAL_CONFIG["modulations"])
def test_all_waveforms_have_requested_shape_and_power(name):
    iq, metadata = generate_iq(name, SIGNAL_CONFIG, np.random.default_rng(7))
    assert iq.shape == (1024,)
    assert iq.dtype == np.complex64
    assert np.mean(np.abs(iq) ** 2) == pytest.approx(1.0, rel=2e-5)
    assert metadata["modulation"] == name


def test_record_start_is_randomized_and_ofdm_bandwidth_matches_rrc():
    offsets = []
    for seed in range(16):
        _, metadata = generate_iq("QPSK", SIGNAL_CONFIG, np.random.default_rng(seed))
        offsets.append(metadata["record_timing_offset_samples"])
    assert len(set(offsets)) > 1
    _, ofdm = generate_iq("OFDM", SIGNAL_CONFIG, np.random.default_rng(99))
    rrc_bandwidth = (1.0 + SIGNAL_CONFIG["pulse_shape"]["rolloff"]) * SIGNAL_CONFIG["symbol_rate"]
    assert ofdm["occupied_bandwidth_hz_approx"] / rrc_bandwidth == pytest.approx(24_000 / 21_600, rel=1e-6)
