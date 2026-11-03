"""V1.1 reliability — OOD score direction/consistency and fail-closed NaN/Inf.

The OOD anomaly scores all obey "higher = more OOD".  This file pins that
direction on peaked (high-confidence ID) vs. uniform (spread OOD) logits, verifies
the Energy log-sum-exp is numerically stable, that batch scoring equals per-sample
scoring, that quantization-scale noise does not flip the ID/OOD ordering, and that
the *metrics* (which gate every OOD report) fail closed on NaN/Inf scores.
"""

from __future__ import annotations

import numpy as np
import pytest

from ood.energy import energy_score
from ood.metrics import auroc, fpr95, oscr, ood_detection_accuracy, ranking_metrics
from ood.scores import compute_scores
from ood.thresholds import decision_at_thresholds, select_thresholds

_METHODS = ("msp", "entropy", "max_logit", "energy")


def _peaked_logits(n: int = 6, c: int = 24) -> np.ndarray:
    """High-confidence ID: one dominant class per sample."""
    logits = np.full((n, c), -5.0)
    logits[np.arange(n), 0] = 8.0
    return logits


def _uniform_logits(n: int = 6, c: int = 24) -> np.ndarray:
    """Uniform logits: maximally spread mass (textbook OOD)."""
    return np.zeros((n, c))


def _fake_int8_quantize(logits: np.ndarray) -> np.ndarray:
    """Coarse symmetric quantization to simulate fake-INT8 numeric noise."""
    peak = float(np.max(np.abs(logits))) or 1.0
    scale = peak / 127.0
    return np.round(logits / scale) * scale


def test_high_confidence_id_scores_lower_than_uniform() -> None:
    id_logits = _peaked_logits()
    ood_logits = _uniform_logits()
    for method in _METHODS:
        id_score = float(compute_scores(id_logits, method).mean())
        ood_score = float(compute_scores(ood_logits, method).mean())
        assert id_score < ood_score, method


def test_energy_logsumexp_stable_on_large_logits() -> None:
    logits = np.full((4, 24), 1e4)
    scores = energy_score(logits)
    assert np.isfinite(scores).all()
    # -T * logsumexp over 24 equal terms = -T * (max + log(24)).
    expected = -(1e4 + np.log(24.0))
    np.testing.assert_allclose(scores, expected, rtol=1e-12)


def test_batch_equals_single_for_energy() -> None:
    rng = np.random.default_rng(2)
    logits = rng.normal(size=(5, 24))
    batch = energy_score(logits, temperature=2.0)
    single = np.array([energy_score(logits[i:i + 1], temperature=2.0)[0]
                       for i in range(logits.shape[0])])
    np.testing.assert_allclose(batch, single, rtol=1e-12, atol=1e-12)


def test_energy_matches_torch_logsumexp() -> None:
    torch = pytest.importorskip("torch")
    rng = np.random.default_rng(1)
    logits = rng.normal(size=(8, 24))
    temperature = 2.0
    np_energy = energy_score(logits, temperature=temperature)
    torch_energy = (-temperature * torch.logsumexp(
        torch.tensor(logits) / temperature, dim=1)).numpy()
    np.testing.assert_allclose(np_energy, torch_energy, rtol=1e-6, atol=1e-6)


def test_fake_int8_does_not_flip_ood_direction() -> None:
    id_logits = _peaked_logits()
    ood_logits = _uniform_logits()
    for method in _METHODS:
        fp32_gap = (compute_scores(ood_logits, method).mean()
                    - compute_scores(id_logits, method).mean())
        q_gap = (compute_scores(_fake_int8_quantize(ood_logits), method).mean()
                 - compute_scores(_fake_int8_quantize(id_logits), method).mean())
        assert fp32_gap > 0 and q_gap > 0, method


def test_temperature_must_be_positive() -> None:
    with pytest.raises(ValueError):
        energy_score(_peaked_logits(), temperature=0.0)
    with pytest.raises(ValueError):
        energy_score(_peaked_logits(), temperature=-1.0)


def test_metrics_fail_closed_on_nan_scores() -> None:
    nan_id = np.array([np.nan, 0.1, 0.2])
    ood = np.array([0.9, 1.0, 1.1])
    with pytest.raises(ValueError):
        auroc(nan_id, ood)
    with pytest.raises(ValueError):
        fpr95(nan_id, ood)
    with pytest.raises(ValueError):
        ranking_metrics(nan_id, ood)


def test_oscr_fail_closed_on_inf_scores() -> None:
    inf_id = np.array([np.inf, 0.1, 0.2])
    ood = np.array([0.9, 1.0, 1.1])
    with pytest.raises(ValueError):
        oscr(inf_id, ood, np.array([True, True, False]))


def test_thresholds_fail_closed_on_nan() -> None:
    id_scores = np.array([np.nan, 0.1, 0.2])
    ood_scores = np.array([0.9, 1.0, 1.1])
    with pytest.raises(ValueError):
        select_thresholds(id_scores, ood_scores)
    with pytest.raises(ValueError):
        decision_at_thresholds(np.array([0.5, np.nan]), {"balanced": {"threshold": 0.5}})


def test_ood_detection_accuracy_value() -> None:
    id_scores = np.array([0.1, 0.2, 0.3, 0.4])   # all below threshold -> accepted
    ood_scores = np.array([0.9, 1.0, 1.1, 1.2])  # all above threshold -> rejected
    acc = ood_detection_accuracy(id_scores, ood_scores, threshold=0.5)
    assert acc == 1.0
    # Flip one ID above and one OOD below: 2 errors out of 8.
    acc2 = ood_detection_accuracy(
        np.array([0.1, 0.6]), np.array([0.4, 1.0]), threshold=0.5)
    assert acc2 == 0.5


def test_ood_detection_accuracy_fails_closed_on_empty() -> None:
    with pytest.raises(ValueError):
        ood_detection_accuracy(np.array([]), np.array([0.5]), threshold=0.5)
    with pytest.raises(ValueError):
        ood_detection_accuracy(np.array([0.5]), np.array([]), threshold=0.5)
