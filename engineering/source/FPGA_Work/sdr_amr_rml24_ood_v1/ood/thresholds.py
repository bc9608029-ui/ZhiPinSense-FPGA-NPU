"""OOD decision thresholds and working points.

Thresholds are locked on OOD *validation* data only, never the final test family.
Three working points are produced, with ``balanced`` as the default.  The primary
constraint is an ID false-reject rate <= 5%.
"""

from __future__ import annotations

from typing import Any

import numpy as np

OOD_WORKING_POINTS = ("conservative", "balanced", "strict")

ID_FRR_TARGET = 0.05
OOD_FAR_TARGET = 0.05


def _as_scores(value: np.ndarray) -> np.ndarray:
    return np.asarray(value, dtype=np.float64).reshape(-1)


def id_false_reject_rate(id_scores: np.ndarray, threshold: float) -> float:
    """Fraction of ID rejected (score > threshold)."""
    id_scores = _as_scores(id_scores)
    if len(id_scores) == 0:
        return float("nan")
    return float(np.mean(id_scores > threshold))


def ood_false_accept_rate(ood_scores: np.ndarray, threshold: float) -> float:
    """Fraction of OOD accepted as known (score <= threshold)."""
    ood_scores = _as_scores(ood_scores)
    if len(ood_scores) == 0:
        return float("nan")
    return float(np.mean(ood_scores <= threshold))


def select_thresholds(id_scores: np.ndarray, ood_scores: np.ndarray,
                      id_frr_target: float = ID_FRR_TARGET,
                      ood_far_target: float = OOD_FAR_TARGET) -> dict[str, dict[str, float]]:
    """Return thresholds for the three frozen working points.

    * conservative — cap ID false-reject at ``id_frr_target`` (keep more ID);
    * strict      — cap OOD false-accept at ``ood_far_target`` (reject more OOD);
    * balanced    — maximize Youden's J = TPR(OOD) - FPR(ID) over the score grid.
    """
    id_scores = _as_scores(id_scores)
    ood_scores = _as_scores(ood_scores)
    if len(id_scores) == 0 or len(ood_scores) == 0:
        raise ValueError("select_thresholds needs non-empty ID and OOD validation scores")

    conservative = float(np.quantile(id_scores, 1.0 - id_frr_target))
    strict = float(np.quantile(ood_scores, ood_far_target))

    candidates = np.unique(np.concatenate([id_scores, ood_scores]))
    best_j = -np.inf
    balanced = float(candidates[len(candidates) // 2])
    for threshold in candidates:
        tpr = float(np.mean(ood_scores > threshold))
        fpr = float(np.mean(id_scores > threshold))
        j = tpr - fpr
        if j > best_j:
            best_j = j
            balanced = float(threshold)

    return {
        "conservative": {
            "threshold": conservative,
            "id_frr": id_false_reject_rate(id_scores, conservative),
            "ood_far": ood_false_accept_rate(ood_scores, conservative),
        },
        "balanced": {
            "threshold": balanced,
            "id_frr": id_false_reject_rate(id_scores, balanced),
            "ood_far": ood_false_accept_rate(ood_scores, balanced),
        },
        "strict": {
            "threshold": strict,
            "id_frr": id_false_reject_rate(id_scores, strict),
            "ood_far": ood_false_accept_rate(ood_scores, strict),
        },
    }


def decision_at_thresholds(scores: np.ndarray, thresholds: dict[str, dict[str, float]]) -> dict[str, np.ndarray]:
    """Apply named thresholds, returning per-sample OOD booleans (True = UNKNOWN)."""
    scores = _as_scores(scores)
    return {
        name: scores > float(spec["threshold"])
        for name, spec in thresholds.items()
    }
