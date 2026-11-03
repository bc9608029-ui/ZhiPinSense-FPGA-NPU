"""OOD metric tests: bounds, separation, and INSUFFICIENT handling."""
import numpy as np
import pytest

from ood import m25b_metrics as mm


def test_auroc_perfect_separation():
    id_scores = np.full(100, -10.0)
    ood_scores = np.full(100, 10.0)
    assert mm.auroc(id_scores, ood_scores) == pytest.approx(1.0)


def test_auroc_chance():
    rng = np.random.default_rng(0)
    id_scores = rng.normal(0, 1, 500)
    ood_scores = rng.normal(0, 1, 500)
    assert 0.4 < mm.auroc(id_scores, ood_scores) < 0.6


def test_aupr_bounds():
    id_scores = np.full(100, -10.0)
    ood_scores = np.full(100, 10.0)
    assert 0.0 <= mm.aupr_in(id_scores, ood_scores) <= 1.0
    assert 0.0 <= mm.aupr_out(id_scores, ood_scores) <= 1.0


def test_fpr95_perfect():
    id_scores = np.full(100, -10.0)
    ood_scores = np.full(100, 10.0)
    assert mm.fpr95(id_scores, ood_scores) == pytest.approx(0.0)


def test_oscr_range():
    id_scores = np.full(100, -10.0)
    ood_scores = np.full(100, 10.0)
    oscr = mm.oscr(id_scores, ood_scores)
    assert 0.0 <= oscr <= 1.0


def test_ood_detection_accuracy_perfect():
    id_scores = np.full(100, -10.0)
    ood_scores = np.full(100, 10.0)
    acc = mm.ood_detection_accuracy(id_scores, ood_scores, threshold=0.0)
    assert acc == pytest.approx(1.0)


def test_insufficient_raises():
    with pytest.raises(ValueError) as exc:
        mm.auroc(np.array([1.0]), np.array([2.0]))
    assert mm.INSUFFICIENT_RESULT in str(exc.value)


def test_summarize_metric_insufficient():
    out = mm.summarize_metric("auroc", mm.auroc, np.array([1.0]), np.array([2.0]))
    assert out["result"] == "INSUFFICIENT"
    assert out["value"] is None
