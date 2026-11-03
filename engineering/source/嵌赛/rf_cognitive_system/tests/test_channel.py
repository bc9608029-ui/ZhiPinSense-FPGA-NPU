import numpy as np
import pytest

from channel.awgn import add_awgn, measure_snr_db
from channel.channel_pipeline import ChannelPipeline


@pytest.mark.parametrize("target", [0.0, 5.0, 10.0, 20.0])
def test_awgn_measured_snr(target):
    rng = np.random.default_rng(123)
    clean = (rng.normal(size=16384) + 1j * rng.normal(size=16384)).astype(np.complex64)
    noisy, metadata = add_awgn(clean, target, np.random.default_rng(456))
    assert measure_snr_db(clean, noisy) == pytest.approx(target, abs=0.02)
    assert metadata["measured_snr_db"] == pytest.approx(target, abs=1e-10)


def test_pipeline_effect_switches_and_metadata():
    config = {
        "domain_randomization": False,
        "awgn": {"enabled": True, "snr_db": 10.0},
        "cfo": {"enabled": True, "hz": 100.0},
        "phase_offset": {"enabled": False},
    }
    clean = np.ones(2048, dtype=np.complex64)
    output, metadata = ChannelPipeline(config, 128_000.0)(clean, np.random.default_rng(9))
    assert output.shape == clean.shape
    assert metadata["effects"] == ["cfo", "awgn"]
    assert metadata["awgn"]["measured_snr_db"] == pytest.approx(10.0, abs=1e-6)


def test_awgn_reference_excludes_interference_power():
    config = {
        "domain_randomization": False,
        "narrowband_interference": {"enabled": True, "sir_db": 0.0},
        "awgn": {"enabled": True, "snr_db": 10.0},
    }
    clean = np.exp(1j * np.linspace(0, 4 * np.pi, 4096)).astype(np.complex64)
    _, metadata = ChannelPipeline(config, 128_000.0)(clean, np.random.default_rng(11))
    desired = metadata["desired_signal_power_before_interference_noise"]
    assert metadata["awgn"]["signal_power"] == pytest.approx(desired, rel=1e-12)
    assert metadata["awgn"]["noise_power"] == pytest.approx(desired / 10.0, rel=1e-10)
