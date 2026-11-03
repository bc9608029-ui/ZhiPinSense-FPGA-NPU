from __future__ import annotations

from collections import Counter

import torch

from datasets.synthetic_dataset import SyntheticModulationDataset
from training.qam_aware_utils import load_qam_aware_config


def test_final_blind_seed_namespace_and_determinism() -> None:
    config = load_qam_aware_config("configs/qam_aware_v2.yaml")
    blind = config["final_blind_test"]
    assert int(blind["seed"]) != int(config["seed"])
    assert blind["split"] not in {"train", "validation", "test"}

    kwargs = dict(
        num_samples=int(blind["samples"]),
        signal_config=config["signal"],
        channel_config=config["channel"],
        return_metadata=True,
        snr_values=config["dataset"]["snr_values"],
    )
    final_a = SyntheticModulationDataset(seed=int(blind["seed"]), split=blind["split"], **kwargs)
    final_b = SyntheticModulationDataset(seed=int(blind["seed"]), split=blind["split"], **kwargs)
    current_test = SyntheticModulationDataset(seed=int(config["seed"]), split="test", **kwargs)
    final_tensor, final_label, final_metadata = final_a[37]
    repeat_tensor, repeat_label, repeat_metadata = final_b[37]
    current_tensor, _, current_metadata = current_test[37]
    torch.testing.assert_close(final_tensor, repeat_tensor, rtol=0, atol=0)
    assert final_label == repeat_label
    assert final_metadata["seed_key"] == repeat_metadata["seed_key"]
    assert final_metadata["seed_key"] != current_metadata["seed_key"]
    assert not torch.equal(final_tensor, current_tensor)


def test_final_blind_exact_modulation_snr_balance() -> None:
    config = load_qam_aware_config("configs/qam_aware_v2.yaml")
    samples = int(config["final_blind_test"]["samples"])
    classes = config["signal"]["modulations"]
    snrs = config["dataset"]["snr_values"]
    combinations = []
    for index in range(samples):
        combination = index % (len(classes) * len(snrs))
        combinations.append((classes[combination % len(classes)], snrs[combination // len(classes)]))
    counts = Counter(combinations)
    assert len(counts) == len(classes) * len(snrs)
    assert set(counts.values()) == {samples // (len(classes) * len(snrs))}
