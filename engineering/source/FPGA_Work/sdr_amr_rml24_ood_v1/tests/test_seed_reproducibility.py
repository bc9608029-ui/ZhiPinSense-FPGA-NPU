"""M9: OOD generation and model initialization must be seed-reproducible."""

from __future__ import annotations

import numpy as np
import torch

from datasets.ood_dataset import generate_ood_records
from models.rml24_net import build_rml24_model
from training.utils import set_seed


def test_ood_records_reproducible_same_seed():
    a = generate_ood_records("far", "ood_final_test", seed=3407, count_per_modulation=2)
    b = generate_ood_records("far", "ood_final_test", seed=3407, count_per_modulation=2)
    np.testing.assert_array_equal(a.iq, b.iq)
    np.testing.assert_array_equal(a.modulation, b.modulation)


def test_ood_records_differ_between_seeds():
    a = generate_ood_records("far", "ood_validation", seed=1, count_per_modulation=2)
    b = generate_ood_records("far", "ood_validation", seed=2, count_per_modulation=2)
    assert not np.array_equal(a.iq, b.iq)


def test_model_initialization_reproducible():
    set_seed(3407)
    first = build_rml24_model(24)
    set_seed(3407)
    second = build_rml24_model(24)
    for (name_a, param_a), (name_b, param_b) in zip(first.state_dict().items(), second.state_dict().items()):
        assert name_a == name_b
        assert torch.equal(param_a, param_b)
