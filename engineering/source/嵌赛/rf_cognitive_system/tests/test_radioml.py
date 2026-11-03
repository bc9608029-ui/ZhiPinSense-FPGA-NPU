import pytest
from pathlib import Path

from datasets.radioml_dataset import radioml_or_synthetic
from datasets.synthetic_dataset import SyntheticModulationDataset


def test_missing_radioml_falls_back_to_synthetic():
    signal = {
        "sample_rate": 128_000.0,
        "symbol_rate": 16_000.0,
        "samples_per_symbol": 8,
        "sample_length": 128,
        "amplitude": 1.0,
        "modulations": ["BPSK", "QPSK"],
    }
    channel = {"domain_randomization": False, "awgn": {"enabled": True, "snr_db": 10.0}}
    missing_path = Path("data/radioml/__test_file_does_not_exist__.hdf5")
    assert not missing_path.exists()
    with pytest.warns(RuntimeWarning, match="Falling back"):
        dataset = radioml_or_synthetic(missing_path, 4, signal, channel, 1)
    assert isinstance(dataset, SyntheticModulationDataset)
    assert dataset[0][0].shape == (2, 128)
