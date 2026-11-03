"""OOD evaluation metrics for the M25-B 24-class OE framework (numpy only).

Scores are OOD-ness (larger = more OOD).  OOD is the positive class for AUROC and
AUPR-OUT; ID is the positive class for AUPR-IN.  ``ood_detection_accuracy`` is the
balanced (ID-accept + OOD-reject)/2 at a fixed threshold.

Insufficient-sample families emit ``24CLASS_OE_RESULT result=INSUFFICIENT`` rather
than fabricating a metric.
"""
from __future__ import annotations

from typing import Any

import numpy as np

INSUFFICIENT_RESULT = "24CLASS_OE_RESULT result=INSUFFICIENT"
MIN_SAMPLES = 2  # minimum samples per side before a metric is meaningful


def _check_sides(id_scores: np.ndarray, ood_scores: np.ndarray) -> None:
    if id_scores.size < MIN_SAMPLES or ood_scores.size < MIN_SAMPLES:
        raise ValueError(INSUFFICIENT_RESULT)


def _average_ranks(x: np.ndarray) -> np.ndarray:
    """1-based average ranks of ``x`` (ties share their mean rank)."""
    x = np.asarray(x, dtype=np.float64)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(x.size, dtype=np.float64)
    n = x.size
    i = 0
    while i < n:
        j = i
        while j + 1 < n and x[order[j + 1]] == x[order[i]]:
            j += 1
        avg = (i + 1 + j + 1) / 2.0
        ranks[order[i:j + 1]] = avg
        i = j + 1
    return ranks


def auroc(id_scores: np.ndarray, ood_scores: np.ndarray) -> float:
    """AUROC with OOD as positive: P(score_OOD > score_ID), ties = 0.5."""
    _check_sides(id_scores, ood_scores)
    id_s = np.asarray(id_scores, dtype=np.float64)
    ood_s = np.asarray(ood_scores, dtype=np.float64)
    n_id, n_ood = id_s.size, ood_s.size
    combined = np.concatenate([id_s, ood_s])
    ranks = _average_ranks(combined)
    ood_rank_sum = ranks[n_id:].sum()
    return float((ood_rank_sum - n_ood * (n_ood + 1.0) / 2.0) / (n_id * n_ood))


def _average_precision(pos_scores: np.ndarray, neg_scores: np.ndarray) -> float:
    """Average precision where ``pos_scores`` is the positive class."""
    pos = np.asarray(pos_scores, dtype=np.float64)
    neg = np.asarray(neg_scores, dtype=np.float64)
    scores = np.concatenate([pos, neg])
    labels = np.concatenate([np.ones(pos.size), np.zeros(neg.size)])
    order = np.argsort(-scores, kind="mergesort")  # descending score
    labels = labels[order]
    n_pos = pos.size
    if n_pos == 0:
        return 0.0
    cum_tp = np.cumsum(labels)
    precision = cum_tp / np.arange(1, labels.size + 1)
    recall = cum_tp / n_pos
    prev_recall = np.concatenate([[0.0], recall[:-1]])
    return float(np.sum((recall - prev_recall) * precision))


def aupr_in(id_scores: np.ndarray, ood_scores: np.ndarray) -> float:
    """AUPR with ID as positive class."""
    _check_sides(id_scores, ood_scores)
    return _average_precision(id_scores, ood_scores)


def aupr_out(id_scores: np.ndarray, ood_scores: np.ndarray) -> float:
    """AUPR with OOD as positive class."""
    _check_sides(id_scores, ood_scores)
    return _average_precision(ood_scores, id_scores)


def fpr95(id_scores: np.ndarray, ood_scores: np.ndarray) -> float:
    """False-positive rate of ID at the threshold achieving 95% OOD true-positive."""
    _check_sides(id_scores, ood_scores)
    id_s = np.asarray(id_scores, dtype=np.float64)
    ood_s = np.asarray(ood_scores, dtype=np.float64)
    thr = np.quantile(ood_s, 0.05)  # score > thr -> 95% of OOD rejected
    return float(np.mean(id_s > thr))


def oscr(id_scores: np.ndarray, ood_scores: np.ndarray) -> float:
    """Open Set Classification Rate: area under (CCR, FPR) curve, normalized."""
    _check_sides(id_scores, ood_scores)
    id_s = np.asarray(id_scores, dtype=np.float64)
    ood_s = np.asarray(ood_scores, dtype=np.float64)
    thr = np.unique(np.concatenate([id_s, ood_s]))
    fpr = np.array([np.mean(ood_s > t) for t in thr])
    ccr = np.array([np.mean(id_s <= t) for t in thr])
    order = np.argsort(fpr)
    fpr, ccr = fpr[order], ccr[order]
    span = fpr[-1] - fpr[0]
    if span <= 0:
        return float(ccr[0])
    return float(np.trapezoid(ccr, fpr) / span)


def ood_detection_accuracy(id_scores: np.ndarray, ood_scores: np.ndarray,
                           threshold: float) -> float:
    """Balanced accuracy at a fixed threshold: 0.5*(ID-accept + OOD-reject)."""
    _check_sides(id_scores, ood_scores)
    id_s = np.asarray(id_scores, dtype=np.float64)
    ood_s = np.asarray(ood_scores, dtype=np.float64)
    id_accept = float(np.mean(id_s <= threshold))
    ood_reject = float(np.mean(ood_s > threshold))
    return float(0.5 * (id_accept + ood_reject))


def id_accept_rate(id_scores: np.ndarray, threshold: float) -> float:
    if id_scores.size < MIN_SAMPLES:
        raise ValueError(INSUFFICIENT_RESULT)
    return float(np.mean(np.asarray(id_scores, dtype=np.float64) <= threshold))


def bootstrap_ci(values: np.ndarray, *, n_boot: int = 1000,
                 alpha: float = 0.05, seed: int = 2026) -> tuple[float, float, float]:
    """Percentile bootstrap 95% CI; returns (mean, lo, hi)."""
    values = np.asarray(values, dtype=np.float64)
    if values.size < MIN_SAMPLES:
        raise ValueError(INSUFFICIENT_RESULT)
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot, dtype=np.float64)
    n = values.size
    for i in range(n_boot):
        means[i] = np.mean(rng.choice(values, size=n, replace=True))
    lo, hi = np.quantile(means, [alpha / 2.0, 1.0 - alpha / 2.0])
    return float(np.mean(values)), float(lo), float(hi)


def summarize_metric(name: str, fn, id_scores: np.ndarray,
                     ood_scores: np.ndarray, **kwargs) -> dict[str, Any]:
    """Run one metric, returning INSUFFICIENT instead of raising on small samples."""
    try:
        value = fn(id_scores, ood_scores, **kwargs)
    except ValueError as exc:
        if INSUFFICIENT_RESULT in str(exc):
            return {"metric": name, "result": "INSUFFICIENT", "value": None}
        raise
    return {"metric": name, "result": "OK", "value": value}


def evaluate_family(id_scores: np.ndarray, ood_scores: np.ndarray,
                    threshold: float | None = None) -> dict[str, Any]:
    """Full metric battery for one (ID, OOD) family pair."""
    metrics: dict[str, Any] = {}
    for name, fn in (
        ("auroc", auroc), ("aupr_in", aupr_in), ("aupr_out", aupr_out),
        ("fpr95", fpr95), ("oscr", oscr),
    ):
        metrics[name] = summarize_metric(name, fn, id_scores, ood_scores)
    if threshold is not None:
        metrics["id_accept_rate"] = summarize_metric(
            "id_accept_rate", lambda a, b, **k: id_accept_rate(a, threshold),
            id_scores, ood_scores)
        metrics["ood_detection_accuracy"] = summarize_metric(
            "ood_detection_accuracy", ood_detection_accuracy,
            id_scores, ood_scores, threshold=threshold)
    return metrics


__all__ = [
    "INSUFFICIENT_RESULT", "MIN_SAMPLES", "auroc", "aupr_in", "aupr_out",
    "fpr95", "oscr", "ood_detection_accuracy", "id_accept_rate",
    "bootstrap_ci", "summarize_metric", "evaluate_family",
]
