"""M13: the OE+Energy loss is finite and consistent with the NumPy Energy score."""

from __future__ import annotations

import numpy as np
import pytest
import torch

from ood.energy import energy_score
from training.oe_energy_loss import energy_score_t, oe_energy_loss


def test_energy_score_t_matches_numpy():
    logits_np = np.random.default_rng(0).normal(size=(6, 5))
    logits_t = torch.from_numpy(logits_np)
    for temperature in (1.0, 2.0):
        np.testing.assert_allclose(
            energy_score_t(logits_t, temperature).numpy(),
            energy_score(logits_np, temperature),
            rtol=1e-5,
        )


def test_oe_energy_loss_finite():
    logits_id = torch.randn(16, 24)
    labels_id = torch.randint(0, 24, (16,))
    logits_ood = torch.randn(16, 24) * 2.0
    total, components = oe_energy_loss(logits_id, labels_id, logits_ood)
    assert torch.isfinite(total)
    assert set(components) == {"ce", "energy_pull_id", "energy_push_ood"}
    for value in components.values():
        assert torch.isfinite(value)


def test_energy_score_t_requires_positive_temperature():
    with pytest.raises(ValueError):
        energy_score_t(torch.zeros(2, 3), temperature=0.0)
