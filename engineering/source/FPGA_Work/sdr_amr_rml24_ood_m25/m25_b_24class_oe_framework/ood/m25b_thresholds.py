"""OOD threshold selection for the M25-B 24-class OE framework.

Thresholds are selected ONLY on the ``ood_validation`` split (never the final
blind split), at three working points:

  - ``id_accept_95``  : threshold where ~95% of ID validation is accepted
  - ``id_accept_99``  : threshold where ~99% of ID validation is accepted (default)
  - ``far_ood``       : threshold where ~95% of far-OOD validation is rejected

Convention follows the deployed 12-class OOD-U: for Energy and the other scores,
a sample is rejected as UNKNOWN when ``score > threshold`` (score is OOD-ness).
"""
from __future__ import annotations

from typing import Any

import numpy as np

DEFAULT_WORKING_POINTS = ("id_accept_95", "id_accept_99", "far_ood")
DEFAULT_ID_ACCEPT = "id_accept_99"
OOD_DIRECTION = "score_gt_threshold_is_ood"  # score > threshold -> reject as UNKNOWN


def _quantile(x: np.ndarray, q: float) -> float:
    x = np.asarray(x, dtype=np.float64)
    if x.size == 0:
        raise ValueError("cannot select a threshold from an empty score array")
    return float(np.quantile(x, q))


def select_thresholds(id_scores: np.ndarray, far_ood_scores: np.ndarray,
                      id_accept_quantiles=(0.95, 0.99),
                      far_reject_quantile: float = 0.95) -> dict[str, float]:
    """Select the three working-point thresholds from validation scores only.

    ``id_scores`` and ``far_ood_scores`` are OOD-ness scores (larger = more OOD).
    """
    id_scores = np.asarray(id_scores, dtype=np.float64)
    far_ood_scores = np.asarray(far_ood_scores, dtype=np.float64)
    if id_scores.size == 0:
        raise ValueError("id_scores must not be empty")
    if far_ood_scores.size == 0:
        raise ValueError("far_ood_scores must not be empty")

    thresholds: dict[str, float] = {}
    for q in sorted(id_accept_quantiles):
        thresholds[f"id_accept_{int(round(q * 100))}"] = _quantile(id_scores, q)
    thresholds["far_ood"] = _quantile(far_ood_scores, far_reject_quantile)
    return thresholds


def apply_threshold(scores: np.ndarray, threshold: float) -> np.ndarray:
    """Return a boolean OOD mask: True where ``score > threshold`` (reject as UNKNOWN)."""
    scores = np.asarray(scores, dtype=np.float64)
    return scores > threshold


def id_accept_rate(id_scores: np.ndarray, threshold: float) -> float:
    if id_scores.size == 0:
        raise ValueError("id_scores must not be empty")
    return float(np.mean(np.asarray(id_scores, dtype=np.float64) <= threshold))


def far_reject_rate(far_ood_scores: np.ndarray, threshold: float) -> float:
    if far_ood_scores.size == 0:
        raise ValueError("far_ood_scores must not be empty")
    return float(np.mean(np.asarray(far_ood_scores, dtype=np.float64) > threshold))


def summarize_thresholds(thresholds: dict[str, float], id_scores: np.ndarray,
                         far_ood_scores: np.ndarray) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, thr in sorted(thresholds.items()):
        out[name] = {
            "threshold": thr,
            "id_accept_rate": id_accept_rate(id_scores, thr),
            "far_reject_rate": far_reject_rate(far_ood_scores, thr),
        }
    return out


__all__ = [
    "DEFAULT_WORKING_POINTS", "DEFAULT_ID_ACCEPT", "OOD_DIRECTION",
    "select_thresholds", "apply_threshold", "id_accept_rate",
    "far_reject_rate", "summarize_thresholds",
]
