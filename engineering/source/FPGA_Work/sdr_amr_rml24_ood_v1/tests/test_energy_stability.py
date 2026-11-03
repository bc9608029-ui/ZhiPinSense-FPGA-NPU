"""M11: the Energy score must match -T*logsumexp and stay finite for extreme logits."""

from __future__ import annotations

import numpy as np
import pytest

from ood.energy import energy_score, free_energy


def test_energy_matches_manual_logsumexp():
    rng = np.random.default_rng(0)
    logits = rng.normal(size=(5, 8)) * 3.0
    for temperature in (1.0, 2.0, 0.5):
        expected = -temperature * np.log(np.exp(logits / temperature).sum(axis=1))
        np.testing.assert_allclose(energy_score(logits, temperature), expected, rtol=1e-10)


def test_energy_stable_for_extreme_logits():
    logits = np.array([
        [-1000.0, 1000.0, 500.0],
        [1e3, -1e3, 0.0],
        [1e6, 1e6, -1e6],
    ])
    result = energy_score(logits)
    assert np.isfinite(result).all()


def test_energy_rejects_bad_input():
    with pytest.raises(ValueError):
        energy_score(np.zeros(3))  # 1-D, needs [N, C]
    with pytest.raises(ValueError):
        energy_score(np.zeros((2, 3)), temperature=0.0)
    with pytest.raises(ValueError):
        energy_score(np.zeros((2, 3)), temperature=-1.0)


def test_free_energy_alias():
    logits = np.array([[1.0, 2.0], [3.0, 4.0]])
    np.testing.assert_array_equal(energy_score(logits), free_energy(logits))
