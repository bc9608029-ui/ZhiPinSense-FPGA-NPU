"""M11: every logits-based anomaly score must rank uniform (OOD) above dominant (ID)."""

from __future__ import annotations

import numpy as np
import pytest

from ood.scores import compute_scores


def test_all_scores_higher_for_uniform_than_dominant():
    id_logits = np.array([
        [10.0, 0.0, 0.0, 0.0],
        [0.0, 8.0, 0.0, 0.0],
    ])
    ood_logits = np.array([
        [0.0, 0.0, 0.0, 0.0],
        [0.2, 0.1, 0.1, -0.1],
    ])
    for name in ("msp", "entropy", "max_logit", "energy"):
        s_id = compute_scores(id_logits, name)
        s_ood = compute_scores(ood_logits, name)
        assert (s_id < s_ood).all(), f"{name} should rank OOD above ID"


def test_scores_are_monotone_with_confidence():
    # More confident ID (larger dominant logit) -> lower anomaly for every method.
    confident = np.array([[50.0, 0.0, 0.0]])
    less_confident = np.array([[5.0, 0.0, 0.0]])
    for name in ("msp", "entropy", "max_logit", "energy"):
        assert compute_scores(confident, name)[0] < compute_scores(less_confident, name)[0]


def test_unknown_method_rejected():
    with pytest.raises(ValueError):
        compute_scores(np.zeros((2, 3)), "not_a_method")
