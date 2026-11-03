"""M12: OOD ranking metrics behave correctly on separable and reversed scores."""

from __future__ import annotations

import numpy as np

from ood.metrics import aupr_in, aupr_out, auroc, fpr95, oscr, ranking_metrics


def test_perfect_separation():
    id_scores = np.array([0.1, 0.2, 0.3, 0.4])
    ood_scores = np.array([0.9, 1.0, 1.1, 1.2])
    assert auroc(id_scores, ood_scores) == 1.0
    assert fpr95(id_scores, ood_scores) == 0.0
    assert aupr_in(id_scores, ood_scores) == 1.0
    assert aupr_out(id_scores, ood_scores) == 1.0


def test_reversed_scores_give_zero_auroc():
    id_scores = np.array([0.9, 1.0, 1.1])
    ood_scores = np.array([0.1, 0.2, 0.3])
    assert auroc(id_scores, ood_scores) == 0.0


def test_ranking_metrics_keys_and_finiteness():
    metrics = ranking_metrics(np.array([0.0, 0.5]), np.array([1.0, 2.0]))
    assert set(metrics) == {"auroc", "aupr_in", "aupr_out", "fpr95"}
    assert all(np.isfinite(value) for value in metrics.values())


def test_oscr_output_shape():
    id_scores = np.array([0.1, 0.3, 0.5, 0.7])
    ood_scores = np.array([1.0, 1.2])
    id_correct = np.array([True, True, False, False])
    out = oscr(id_scores, ood_scores, id_correct)
    assert set(out) == {"curve", "auc_ccr_fpr"}
    assert isinstance(out["auc_ccr_fpr"], float)


def test_oscr_length_mismatch_raises():
    with np.testing.assert_raises(ValueError):
        oscr(np.array([0.1, 0.2]), np.array([1.0]), np.array([True]))


def test_empty_inputs_give_nan():
    assert np.isnan(auroc(np.array([]), np.array([0.5])))
    assert np.isnan(fpr95(np.array([0.1]), np.array([])))
