"""OOD ranking metrics (pure NumPy, no sklearn/torch).

All inputs are anomaly scores: higher means more likely OOD.  ``id_scores`` are
scores of known/in-distribution samples, ``ood_scores`` are scores of
out-of-distribution samples.
"""

from __future__ import annotations

from typing import Callable

import numpy as np


def _as_scores(value: np.ndarray) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float64).reshape(-1)
    if not np.isfinite(arr).all():
        raise ValueError("OOD scores contain non-finite (NaN/Inf) values; refusing to rank")
    return arr


def _average_ranks(scores: np.ndarray) -> np.ndarray:
    """1-based average ranks with tie handling."""
    n = len(scores)
    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    ranks = np.empty(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    return ranks


def auroc(id_scores: np.ndarray, ood_scores: np.ndarray) -> float:
    """Area under the ROC curve, treating OOD as the positive class."""
    id_scores = _as_scores(id_scores)
    ood_scores = _as_scores(ood_scores)
    if len(id_scores) == 0 or len(ood_scores) == 0:
        return float("nan")
    pooled = np.concatenate([id_scores, ood_scores])
    ranks = _average_ranks(pooled)
    n_ood = len(ood_scores)
    rank_ood = ranks[len(id_scores):]
    u = rank_ood.sum() - n_ood * (n_ood + 1) / 2.0
    return float(u / (len(id_scores) * n_ood))


def _aupr(positive_scores: np.ndarray, negative_scores: np.ndarray) -> float:
    """AUPR where the positive class has *higher* score."""
    positive_scores = _as_scores(positive_scores)
    negative_scores = _as_scores(negative_scores)
    if len(positive_scores) == 0:
        return float("nan")
    if len(negative_scores) == 0:
        return 1.0
    scores = np.concatenate([positive_scores, negative_scores])
    labels = np.concatenate([np.ones(len(positive_scores)), np.zeros(len(negative_scores))])
    order = np.argsort(-scores, kind="mergesort")
    sorted_labels = labels[order]
    tp = np.cumsum(sorted_labels)
    precision = tp / np.arange(1, len(sorted_labels) + 1)
    recall = tp / tp[-1]
    ap = 0.0
    prev_recall = 0.0
    for i in range(len(sorted_labels)):
        if sorted_labels[i] == 1:
            ap += precision[i] * (recall[i] - prev_recall)
            prev_recall = recall[i]
    return float(ap)


def aupr_in(id_scores: np.ndarray, ood_scores: np.ndarray) -> float:
    """AUPR with ID as positive; ID has *lower* anomaly score, so negate."""
    return _aupr(-id_scores, -ood_scores)


def aupr_out(id_scores: np.ndarray, ood_scores: np.ndarray) -> float:
    """AUPR with OOD as positive; OOD has higher anomaly score."""
    return _aupr(ood_scores, id_scores)


def fpr95(id_scores: np.ndarray, ood_scores: np.ndarray) -> float:
    """False-positive rate of ID when the OOD true-positive rate is 95%."""
    id_scores = _as_scores(id_scores)
    ood_scores = _as_scores(ood_scores)
    if len(ood_scores) == 0:
        return float("nan")
    threshold = float(np.quantile(ood_scores, 0.05))
    if len(id_scores) == 0:
        return float("nan")
    return float(np.mean(id_scores > threshold))


def oscr(id_scores: np.ndarray, ood_scores: np.ndarray, id_correct: np.ndarray,
         n_points: int = 200) -> dict[str, object]:
    """Open-Set Classification Rate curve (CCR vs FPR).

    ``id_correct`` marks whether each ID sample was correctly classified by the
    closed-set classifier.  For a threshold ``t``, ID with ``score <= t`` are
    accepted and OOD with ``score > t`` are rejected; FPR is the fraction of ID
    rejected and CCR is the accuracy over accepted ID.
    """
    id_scores = _as_scores(id_scores)
    ood_scores = _as_scores(ood_scores)
    id_correct = np.asarray(id_correct, dtype=bool).reshape(-1)
    if len(id_scores) != len(id_correct):
        raise ValueError("id_scores and id_correct must have equal length")
    if len(id_scores) == 0 or len(ood_scores) == 0:
        return {"curve": [], "auc_ccr_fpr": float("nan")}

    thresholds = np.unique(id_scores)
    if len(thresholds) > n_points:
        thresholds = thresholds[np.linspace(0, len(thresholds) - 1, n_points).astype(int)]
    curve: list[list[float]] = []
    for threshold in thresholds:
        accepted = id_scores <= threshold
        fpr = float(np.mean(id_scores > threshold))
        if not bool(accepted.any()):
            continue
        ccr = float(np.mean(id_correct[accepted]))
        curve.append([fpr, ccr])
    curve = sorted(curve, key=lambda point: point[0])
    if len(curve) < 2:
        auc = float(curve[0][1]) if curve else float("nan")
    else:
        xs = np.array([p[0] for p in curve])
        ys = np.array([p[1] for p in curve])
        auc = float(np.trapezoid(ys, xs))
    return {"curve": curve, "auc_ccr_fpr": auc}


def ranking_metrics(id_scores: np.ndarray, ood_scores: np.ndarray) -> dict[str, float]:
    """AUROC / AUPR-IN / AUPR-OUT / FPR95 in one call."""
    return {
        "auroc": auroc(id_scores, ood_scores),
        "aupr_in": aupr_in(id_scores, ood_scores),
        "aupr_out": aupr_out(id_scores, ood_scores),
        "fpr95": fpr95(id_scores, ood_scores),
    }


def ood_detection_accuracy(id_scores: np.ndarray, ood_scores: np.ndarray,
                           threshold: float) -> float:
    """Frozen-threshold OOD detection accuracy.

    Scores are anomaly scores where **higher means more OOD**.  A sample is
    correct when an ID sample is accepted as known (``score <= threshold``) or an
    OOD sample is rejected as unknown (``score > threshold``).  The value is the
    overall accuracy ``(n_id_correct + n_ood_correct) / (n_id + n_ood)``.

    This is the single frozen-threshold summary used on the *final* test split:
    the threshold is locked on validation (see ``ood/threshold_manifest.py``) and
    only applied here, so the metric never re-fits on test data.
    """
    id_scores = _as_scores(id_scores)
    ood_scores = _as_scores(ood_scores)
    n_id, n_ood = len(id_scores), len(ood_scores)
    if n_id == 0 or n_ood == 0:
        raise ValueError("ood_detection_accuracy needs non-empty ID and OOD scores")
    correct_id = float(np.sum(id_scores <= threshold))
    correct_ood = float(np.sum(ood_scores > threshold))
    return (correct_id + correct_ood) / (n_id + n_ood)


def bootstrap_ci(metric_fn: Callable[..., float], *arrays: np.ndarray,
                 n_boot: int = 1000, seed: int = 3407, alpha: float = 0.05) -> dict[str, float]:
    """Percentile bootstrap confidence interval for ``metric_fn(*arrays)``."""
    arrays = [np.asarray(a, dtype=np.float64) for a in arrays]
    rng = np.random.default_rng(int(seed))
    estimate = float(metric_fn(*arrays))
    estimates: list[float] = []
    for _ in range(int(n_boot)):
        sampled = [a[rng.integers(0, len(a), size=len(a))] for a in arrays]
        estimates.append(float(metric_fn(*sampled)))
    lower = float(np.percentile(estimates, 100 * alpha / 2))
    upper = float(np.percentile(estimates, 100 * (1 - alpha / 2)))
    return {"estimate": estimate, "lower": lower, "upper": upper, "n_boot": int(n_boot)}
