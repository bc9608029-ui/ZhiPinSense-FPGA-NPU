import numpy as np
import torch
from collections import Counter

from datasets.synthetic_dataset import SyntheticModulationDataset
from models.baseline_cnn import BaselineCNN, model_profile


SIGNAL = {
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
CHANNEL = {
    "domain_randomization": True,
    "awgn": {"enabled": True, "probability": 1.0, "snr_db": [0.0, 20.0]},
    "cfo": {"enabled": True, "probability": 0.5, "hz": [-500.0, 500.0]},
}


def test_dataset_shape_metadata_and_determinism():
    first = SyntheticModulationDataset(16, SIGNAL, CHANNEL, seed=77, return_metadata=True)
    second = SyntheticModulationDataset(16, SIGNAL, CHANNEL, seed=77, return_metadata=True)
    x1, y1, metadata = first[3]
    x2, y2, _ = second[3]
    assert x1.shape == (2, 1024)
    assert x1.dtype == torch.float32
    assert y1 == y2 == 3
    assert torch.equal(x1, x2)
    assert metadata["signal"]["modulation"] == "16QAM"
    assert "measured_snr_db" in metadata["channel"]["awgn"]


def test_epoch_changes_online_sample_but_is_reproducible():
    dataset = SyntheticModulationDataset(8, SIGNAL, CHANNEL, seed=2)
    before = dataset[0][0]
    dataset.set_epoch(1)
    after = dataset[0][0]
    assert not torch.equal(before, after)
    clone = SyntheticModulationDataset(8, SIGNAL, CHANNEL, seed=2)
    clone.set_epoch(1)
    assert torch.equal(after, clone[0][0])


def test_validation_and_test_ignore_epoch_and_do_not_overlap():
    validation = SyntheticModulationDataset(8, SIGNAL, CHANNEL, seed=2, split="validation")
    test = SyntheticModulationDataset(8, SIGNAL, CHANNEL, seed=2, split="test")
    validation_before = validation[0][0]
    validation.set_epoch(99)
    assert torch.equal(validation_before, validation[0][0])
    assert not torch.equal(validation_before, test[0][0])


def test_modulation_snr_stratification_is_exact():
    snrs = [-2.0, 0.0, 2.0]
    dataset = SyntheticModulationDataset(
        48, SIGNAL, CHANNEL, seed=3, split="test", return_metadata=True, snr_values=snrs
    )
    pairs = Counter()
    for index in range(len(dataset)):
        _, label, metadata = dataset[index]
        pairs[(label, metadata["assigned_snr_db"])] += 1
    assert len(pairs) == len(SIGNAL["modulations"]) * len(snrs)
    assert set(pairs.values()) == {2}


def test_model_forward_shape_and_profile():
    model = BaselineCNN(num_classes=8, base_channels=16)
    output = model(torch.randn(4, 2, 1024))
    assert output.shape == (4, 8)
    profile = model_profile(model, 1024)
    assert profile["parameters"] > 0
    assert profile["approx_flops"] > profile["parameters"]
