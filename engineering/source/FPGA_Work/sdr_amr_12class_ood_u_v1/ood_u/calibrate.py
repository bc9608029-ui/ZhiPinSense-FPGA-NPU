"""Method selection + threshold/temperature freeze on ``ood_validation``.

Method selection is a rank aggregation across near/far/overall AUROC, FPR95,
OSCR and the impaired-ID accept rate (never AUROC alone).  Energy's temperature
is scanned on validation only, and the three frozen working points
(id_accept_95 / id_accept_99 / far_ood_target) are produced from validation ID
and far-OOD scores.  Nothing here touches ``ood_final_test``.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ood.metrics import auroc
from ood.scores import compute_scores
from ood_u import contract
from ood_u.benchmark import logits_for
from ood_u.data import SplitRecords
from ood_u.model import ADAMRV11Net

TEMPERATURE_SCAN = (0.5, 1.0, 2.0, 5.0)
# Impaired-ID accept below this fraction (at the 99% accept point) disqualifies a
# method: it would reject too many known-but-impaired signals as UNKNOWN.
IMPAIRED_ACCEPT_FLOOR = 0.90


def select_method(benchmark_report: dict[str, Any]) -> tuple[str, dict[str, int]]:
    """Choose the best method by aggregated rank across six criteria."""
    methods = benchmark_report["methods"]
    names = list(methods)
    if set(names) != set(contract.SCORE_METHODS):
        raise ValueError("benchmark report does not cover all five OOD-U methods")

    criteria: dict[str, list[float]] = {
        "auroc_near": [methods[n]["near"]["auroc"] for n in names],
        "auroc_far": [methods[n]["far"]["auroc"] for n in names],
        "auroc_overall": [methods[n]["overall"]["auroc"] for n in names],
        "fpr95_overall": [methods[n]["overall"]["fpr95"] for n in names],
        "oscr_overall": [methods[n]["overall"]["oscr_auc"] for n in names],
        "impaired_id_accept": [methods[n]["impaired_id_accept_at_99pct"] for n in names],
    }
    higher_better = {"auroc_near", "auroc_far", "auroc_overall", "oscr_overall", "impaired_id_accept"}

    for cname, values in criteria.items():
        if not np.isfinite(values).all():
            raise ValueError(f"benchmark criterion {cname!r} contains non-finite values; cannot select")

    ranks: dict[str, int] = {n: 0 for n in names}
    for cname, values in criteria.items():
        order = np.argsort(values)
        if cname in higher_better:
            order = order[::-1]
        for rank, idx in enumerate(order):
            ranks[names[int(idx)]] += int(rank)

    # Tie-break on overall AUROC (higher is better).
    chosen = min(names, key=lambda n: (ranks[n], -methods[n]["overall"]["auroc"]))
    return chosen, ranks


def pick_temperature(id_logits: np.ndarray, near_logits: np.ndarray,
                     far_logits: np.ndarray) -> float:
    """Scan Energy temperature on validation; maximize overall AUROC."""
    overall = np.concatenate([near_logits, far_logits])
    best_t, best_auc = 1.0, -np.inf
    for t in TEMPERATURE_SCAN:
        id_s = compute_scores(id_logits, "energy", t)
        ood_s = compute_scores(overall, "energy", t)
        auc = auroc(id_s, ood_s)
        if auc > best_auc:
            best_auc, best_t = auc, t
    return best_t


def compute_working_points(id_scores: np.ndarray, near_scores: np.ndarray,
                           far_scores: np.ndarray) -> dict[str, dict[str, float]]:
    """Three frozen working points (higher = more OOD)."""
    def _reject(scores: np.ndarray, threshold: float) -> float:
        return float(np.mean(scores > threshold)) if len(scores) else float("nan")

    t95 = float(np.quantile(id_scores, 0.95))
    t99 = float(np.quantile(id_scores, 0.99))
    t_far = float(np.quantile(far_scores, 0.05)) if len(far_scores) else float("nan")

    return {
        "id_accept_95": {
            "threshold": t95,
            "id_accept_rate": 0.95,
            "id_frr": float(np.mean(id_scores > t95)),
            "near_reject_rate": _reject(near_scores, t95),
            "far_reject_rate": _reject(far_scores, t95),
        },
        "id_accept_99": {
            "threshold": t99,
            "id_accept_rate": 0.99,
            "id_frr": float(np.mean(id_scores > t99)),
            "near_reject_rate": _reject(near_scores, t99),
            "far_reject_rate": _reject(far_scores, t99),
        },
        "far_ood_target": {
            "threshold": t_far,
            "far_reject_rate": 0.95,
            "id_accept_rate": float(np.mean(id_scores <= t_far)),
            "near_reject_rate": _reject(near_scores, t_far),
            "id_frr": float(np.mean(id_scores > t_far)),
        },
    }


def calibrate(
    model: ADAMRV11Net,
    id_val: SplitRecords,
    near_val: SplitRecords,
    far_val: SplitRecords,
    *,
    chosen_method: str,
) -> dict[str, Any]:
    """Freeze method/temperature/working-points from validation data only."""
    if chosen_method not in contract.SCORE_METHODS:
        raise ValueError(f"chosen_method {chosen_method!r} not in {contract.SCORE_METHODS}")

    id_logits = logits_for(model, id_val)
    near_logits = logits_for(model, near_val)
    far_logits = logits_for(model, far_val)

    temperature = pick_temperature(id_logits, near_logits, far_logits) if chosen_method == "energy" else 1.0
    id_s = compute_scores(id_logits, chosen_method, temperature)
    near_s = compute_scores(near_logits, chosen_method, temperature)
    far_s = compute_scores(far_logits, chosen_method, temperature)
    working_points = compute_working_points(id_s, near_s, far_s)

    default_threshold = float(working_points[contract.DEFAULT_WORKING_POINT]["threshold"])
    return {
        "score_method": chosen_method,
        "temperature": temperature,
        "threshold": default_threshold,
        "working_points": working_points,
        "target_operating_point": contract.DEFAULT_WORKING_POINT,
    }


__all__ = ["select_method", "pick_temperature", "compute_working_points", "calibrate",
           "TEMPERATURE_SCAN", "IMPAIRED_ACCEPT_FLOOR"]
