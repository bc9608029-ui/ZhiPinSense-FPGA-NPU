"""Unit tests for the config-driven robust augmentation module (PROVISIONAL).

14 tests, NumPy-only (does not import torch).  Run from the project root:

    python -m pytest tests/test_robust_augment.py -q
"""

from __future__ import annotations

import numpy as np
import pytest

from channel.robust_augment import (
    EFFECT_ORDER,
    RobustChannelPipeline,
    build_domain_config,
    sample_parameter,
)

SAMPLE_RATE = 128000.0
N = 1024


def _iq(seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(N) + 1j * rng.standard_normal(N)).astype(np.complex64)


def _seeded(seed: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([seed]))


def _disabled_channel() -> dict:
    """All effects disabled; nothing applied when no snr_db is passed."""
    return {
        "domain_randomization": True,
        "awgn": {"enabled": False, "probability": 0.0, "snr_db": [-20.0, 20.0]},
        "rayleigh": {"enabled": False, "probability": 0.0},
        "rician": {"enabled": False, "probability": 0.0, "k_factor": [3.0, 10.0]},
        "multipath": {"enabled": False, "probability": 0.0, "num_taps": [2, 4], "max_delay": 10},
        "cfo": {"enabled": False, "probability": 0.0, "hz": [-1200.0, 1200.0]},
        "phase_offset": {"enabled": False, "probability": 0.0, "radians": [-3.14159, 3.14159]},
        "phase_noise": {"enabled": False, "probability": 0.0, "std_rad": [0.0001, 0.003]},
        "sfo": {"enabled": False, "probability": 0.0, "ppm": [-60.0, 60.0]},
        "iq_imbalance": {"enabled": False, "probability": 0.0, "gain_db": [-1.0, 1.0], "phase_deg": [-5.0, 5.0]},
        "dc_offset": {"enabled": False, "probability": 0.0, "magnitude": [0.0, 0.05]},
        "amplitude_scaling": {"enabled": False, "probability": 0.0, "scale": [0.7, 1.3]},
        "clipping": {"enabled": False, "probability": 0.0, "level_rms": [1.5, 2.5]},
        "narrowband_interference": {"enabled": False, "probability": 0.0, "sir_db": [8.0, 25.0]},
        "burst_interference": {"enabled": False, "probability": 0.0, "sir_db": [5.0, 20.0], "duty_cycle": [0.05, 0.2]},
    }


_DOMAIN_SPECS = {
    "cfo_strong": {"cfo": {"hz": [-2500.0, 2500.0]}},
    "multipath": {"multipath": {"num_taps": [3, 6], "max_delay": 20}},
    "multi_impairment": {
        "cfo": {"hz": [-1800.0, 1800.0]},
        "phase_noise": {"std_rad": [0.002, 0.008]},
        "iq_imbalance": {"gain_db": [-1.5, 1.5], "phase_deg": [-8.0, 8.0]},
        "multipath": {"num_taps": [2, 5], "max_delay": 16},
    },
}


# --- contract / sampling helpers -------------------------------------------------

def test_effect_order_matches_baseline():
    assert EFFECT_ORDER == (
        "rayleigh", "rician", "multipath", "cfo", "phase_offset", "phase_noise", "sfo",
        "iq_imbalance", "dc_offset", "amplitude_scaling", "clipping",
        "narrowband_interference", "burst_interference",
    )


def test_sample_parameter_scalar_is_fixed():
    rng = _seeded(0)
    assert sample_parameter(1.25, rng) == 1.25
    assert sample_parameter(7, rng, integer=True) == 7


def test_sample_parameter_range_within_bounds():
    rng = _seeded(1)
    values = [sample_parameter([2.0, 3.0], rng) for _ in range(200)]
    assert all(2.0 <= v <= 3.0 for v in values)


def test_sample_parameter_integer_inclusive():
    rng = _seeded(2)
    values = {sample_parameter([2, 4], rng, integer=True) for _ in range(500)}
    assert values == {2, 3, 4}


def test_sample_parameter_rejects_inverted_range():
    rng = _seeded(3)
    with pytest.raises(ValueError):
        sample_parameter([3.0, 2.0], rng)


# --- validation (fail closed) -----------------------------------------------------

def test_fail_closed_on_unknown_effect_and_missing_range():
    # Unknown effect key is rejected at construction.
    with pytest.raises(ValueError):
        RobustChannelPipeline({"mystery_effect": {"enabled": True}}, SAMPLE_RATE)
    # An enabled effect with no range must not silently default.
    config = _disabled_channel()
    config["cfo"]["enabled"] = True
    config["cfo"]["probability"] = 1.0
    del config["cfo"]["hz"]
    pipeline = RobustChannelPipeline(config, SAMPLE_RATE)
    with pytest.raises((KeyError, ValueError, TypeError)):
        pipeline(_iq(), _seeded(4))


# --- pipeline behavior -------------------------------------------------------------

def test_output_shape_and_dtype():
    config = _disabled_channel()
    config["phase_noise"]["enabled"] = True
    config["phase_noise"]["probability"] = 1.0
    out, _ = RobustChannelPipeline(config, SAMPLE_RATE)(_iq(), _seeded(5))
    assert out.dtype == np.complex64
    assert out.shape == (N,)


def test_all_disabled_passthrough():
    iq = _iq()
    out, metadata = RobustChannelPipeline(_disabled_channel(), SAMPLE_RATE)(iq, _seeded(6))
    assert np.array_equal(out, iq)
    assert metadata["effects"] == []


def test_cfo_preserves_power_and_records_hz():
    config = _disabled_channel()
    config["cfo"]["enabled"] = True
    config["cfo"]["probability"] = 1.0
    config["cfo"]["hz"] = [100.0, 200.0]
    iq = _iq(7)
    out, metadata = RobustChannelPipeline(config, SAMPLE_RATE)(iq, _seeded(7))
    # CFO is a pure per-sample phase rotation: power is preserved exactly.
    assert np.isclose(np.mean(np.abs(out) ** 2), np.mean(np.abs(iq) ** 2), rtol=1e-6)
    assert not np.allclose(out, iq)
    assert 100.0 <= metadata["cfo_hz"] <= 200.0


def test_multipath_unit_norm_energy():
    config = _disabled_channel()
    config["multipath"]["enabled"] = True
    config["multipath"]["probability"] = 1.0
    iq = _iq(8)
    out, metadata = RobustChannelPipeline(config, SAMPLE_RATE)(iq, _seeded(8))
    # Baseline multipath normalizes tap energy to unit norm.
    assert np.isclose(np.mean(np.abs(out) ** 2), np.mean(np.abs(iq) ** 2), rtol=0.05)
    assert "multipath" in metadata and "delays" in metadata["multipath"]


def test_awgn_metadata_snr_consistent():
    config = _disabled_channel()
    out, metadata = RobustChannelPipeline(config, SAMPLE_RATE)(_iq(9), _seeded(9), snr_db=10.0)
    assert abs(metadata["awgn"]["target_snr_db"] - 10.0) < 1e-9
    assert abs(metadata["awgn"]["measured_snr_db"] - 10.0) < 0.5
    assert "awgn" in metadata["effects"]


def test_deterministic_with_seeded_rng():
    config = _disabled_channel()
    config["domain_randomization"] = False
    for name in ("multipath", "cfo", "phase_noise", "iq_imbalance"):
        config[name]["enabled"] = True
        config[name]["probability"] = 1.0
    pipeline = RobustChannelPipeline(config, SAMPLE_RATE)
    iq = _iq(10)
    out1, meta1 = pipeline(iq, _seeded(11), snr_db=5.0)
    out2, meta2 = pipeline(iq, _seeded(11), snr_db=5.0)
    assert np.array_equal(out1, out2)
    assert meta1 == meta2


# --- domain config derivation -------------------------------------------------------

def test_domain_spec_disables_unrelated():
    cfg = build_domain_config(_disabled_channel(), "cfo_strong", _DOMAIN_SPECS)
    assert cfg["domain_randomization"] is False
    assert cfg["cfo"]["enabled"] is True and cfg["cfo"]["probability"] == 1.0
    assert cfg["cfo"]["hz"] == [-2500.0, 2500.0]
    assert cfg["awgn"]["enabled"] is True and cfg["awgn"]["probability"] == 1.0
    assert cfg["multipath"]["enabled"] is False and cfg["multipath"]["probability"] == 0.0
    assert cfg["phase_noise"]["enabled"] is False


def test_domain_spec_unknown_domain_raises():
    with pytest.raises(KeyError):
        build_domain_config(_disabled_channel(), "does_not_exist", _DOMAIN_SPECS)
