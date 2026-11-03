"""M12: thresholds lock on the three frozen working points with the FRR/FAR caps."""

from __future__ import annotations

import numpy as np

from ood.thresholds import OOD_WORKING_POINTS, decision_at_thresholds, select_thresholds


def _validation_scores(n: int = 1000):
    return np.linspace(0.0, 1.0, n), np.linspace(2.0, 3.0, n)


def test_three_named_working_points():
    id_scores, ood_scores = _validation_scores()
    thresholds = select_thresholds(id_scores, ood_scores)
    assert tuple(thresholds) == OOD_WORKING_POINTS
    for name in OOD_WORKING_POINTS:
        assert set(thresholds[name]) == {"threshold", "id_frr", "ood_far"}


def test_conservative_caps_id_frr():
    id_scores, ood_scores = _validation_scores()
    thresholds = select_thresholds(id_scores, ood_scores, id_frr_target=0.05)
    assert thresholds["conservative"]["id_frr"] <= 0.05 + 1e-9


def test_strict_caps_ood_far():
    id_scores, ood_scores = _validation_scores()
    thresholds = select_thresholds(id_scores, ood_scores, ood_far_target=0.05)
    assert thresholds["strict"]["ood_far"] <= 0.05 + 1e-9


def test_balanced_between_the_other_two():
    id_scores, ood_scores = _validation_scores()
    thresholds = select_thresholds(id_scores, ood_scores)
    assert thresholds["conservative"]["threshold"] <= thresholds["balanced"]["threshold"] <= \
        thresholds["strict"]["threshold"]


def test_decision_is_boolean_and_shaped():
    id_scores, ood_scores = _validation_scores(100)
    thresholds = select_thresholds(id_scores, ood_scores)
    scores = np.array([0.0, 0.5, 1.0, 2.5, 3.0])
    decisions = decision_at_thresholds(scores, thresholds)
    for name in OOD_WORKING_POINTS:
        assert decisions[name].dtype == bool
        assert decisions[name].shape == scores.shape
