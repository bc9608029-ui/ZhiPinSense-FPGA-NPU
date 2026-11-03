"""Threshold tests: working points, direction, and id-accept quantiles."""
import numpy as np
import pytest

from ood import m25b_thresholds as t


def test_select_thresholds_keys():
    id_scores = np.random.default_rng(0).normal(-5.0, 1.0, size=1000)
    far_scores = np.random.default_rng(1).normal(5.0, 1.0, size=1000)
    th = t.select_thresholds(id_scores, far_scores)
    assert set(th.keys()) == {"id_accept_95", "id_accept_99", "far_ood"}


def test_accept_quantile_order():
    id_scores = np.random.default_rng(0).normal(-5.0, 1.0, size=2000)
    far_scores = np.random.default_rng(1).normal(5.0, 1.0, size=2000)
    th = t.select_thresholds(id_scores, far_scores)
    assert th["id_accept_99"] > th["id_accept_95"]


def test_apply_threshold_direction():
    scores = np.array([0.0, 0.5, 1.0])
    mask = t.apply_threshold(scores, 0.5)
    # score > threshold -> OOD; 0.0 and 0.5 are NOT OOD, 1.0 is.
    assert mask.tolist() == [False, False, True]


def test_id_accept_rate_matches_quantile():
    rng = np.random.default_rng(7)
    id_scores = rng.normal(-5.0, 1.0, size=5000)
    far_scores = rng.normal(5.0, 1.0, size=5000)
    th = t.select_thresholds(id_scores, far_scores)
    rate = t.id_accept_rate(id_scores, th["id_accept_99"])
    assert abs(rate - 0.99) < 0.02


def test_summarize_thresholds():
    rng = np.random.default_rng(3)
    id_scores = rng.normal(-5.0, 1.0, size=1000)
    far_scores = rng.normal(5.0, 1.0, size=1000)
    th = t.select_thresholds(id_scores, far_scores)
    summary = t.summarize_thresholds(th, id_scores, far_scores)
    assert "id_accept_99" in summary
    assert "far_ood" in summary
