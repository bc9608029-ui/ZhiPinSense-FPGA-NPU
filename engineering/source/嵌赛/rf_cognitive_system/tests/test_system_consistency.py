import numpy as np

from deployment.numerical_contract import (
    NumericalContract,
    consistency_metrics,
    planned_fpga_tensors_from_int16,
    reference_tensors_from_int16,
)
from datasets.synthetic_dataset import SyntheticModulationDataset
from dsp.wideband_discovery import DiscoveryConfig, discover_signals, extract_signal_frame
from training.qam_aware_utils import load_qam_aware_config
from training.utils import load_config


def test_sdr_int16_fixed_frontend_matches_float_reference_after_quantization() -> None:
    rng = np.random.default_rng(20260909)
    iq = np.clip(np.rint(rng.normal(0.0, 6000.0, size=(1024, 2))), -32768, 32767).astype(np.int16)
    contract = NumericalContract()
    reference = reference_tensors_from_int16(iq, contract)
    planned = planned_fpga_tensors_from_int16(iq, contract)
    metrics = consistency_metrics(reference, planned)
    assert metrics["iq_float_max_abs_error"] == 0.0
    assert metrics["physical_float_max_abs_error"] == 0.0
    assert metrics["iq_int8_exact_match"] is True
    assert metrics["physical_int8_exact_match"] is True


def test_wideband_discovery_finds_two_separated_signals() -> None:
    rng = np.random.default_rng(12)
    sample_rate = 1_024_000.0
    length = 8192
    n = np.arange(length)
    iq = 1.0 * np.exp(1j * 2.0 * np.pi * 120_000.0 * n / sample_rate)
    iq += 0.8 * np.exp(1j * 2.0 * np.pi * -210_000.0 * n / sample_rate)
    iq += 0.05 * (rng.normal(size=length) + 1j * rng.normal(size=length))
    result = discover_signals(iq, sample_rate, DiscoveryConfig(threshold_db=10.0))
    centers = sorted(item["center_frequency_hz"] for item in result["detections"])
    assert len(centers) == 2
    assert abs(centers[0] + 210_000.0) < 2_500.0
    assert abs(centers[1] - 120_000.0) < 2_500.0


def test_ddc_extraction_returns_time_power_phase_frame_shape() -> None:
    sample_rate = 1_024_000.0
    n = np.arange(16384)
    iq = np.exp(1j * 2.0 * np.pi * 180_000.0 * n / sample_rate)
    frame, metadata = extract_signal_frame(iq, sample_rate, 180_000.0, 40_000.0)
    assert frame.shape == (1024,)
    assert frame.dtype == np.complex64
    assert np.isfinite(frame).all()
    assert metadata["target_sample_rate_hz"] == 128_000.0


def test_v2_inherits_frozen_signal_channel_and_dataset_contract() -> None:
    baseline = load_config("configs/baseline.yaml")
    v2 = load_qam_aware_config("configs/qam_aware_v2.yaml")
    assert v2["signal"] == baseline["signal"]
    assert v2["channel"] == baseline["channel"]
    assert v2["dataset"] == baseline["dataset"]


def test_formal_dataset_explicit_snr_uses_balanced_list_not_awgn_range() -> None:
    config = load_qam_aware_config("configs/qam_aware_v2.yaml")
    dataset = SyntheticModulationDataset(
        8,
        config["signal"],
        config["channel"],
        seed=int(config["seed"]),
        split="validation",
        return_metadata=True,
        snr_values=config["dataset"]["snr_values"],
    )
    _, _, metadata = dataset[0]
    assert metadata["assigned_snr_db"] == -20.0
    assert metadata["channel"]["awgn"]["target_snr_db"] == -20.0
    assert "awgn" in metadata["channel"]["effects"]
