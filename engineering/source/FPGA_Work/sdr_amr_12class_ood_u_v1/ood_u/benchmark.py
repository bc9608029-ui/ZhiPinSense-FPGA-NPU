"""Score benchmark: compare the five OOD-U scores on the ``ood_validation`` split.

For each method the ID, near_12, far, ambiguous and impaired-ID logits are scored
with the shared ``ood`` primitives (higher = more OOD), and the ranking metrics
(AUROC / AUPR-IN / AUPR-OUT / FPR95 / OSCR), the ID false-reject rate at the 99%
accept point, and the impaired-ID accept rate are reported.  Ambiguous is a side
report and never enters the main method selection.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ood.metrics import aupr_in, aupr_out, auroc, fpr95, oscr
from ood.scores import compute_scores
from ood.thresholds import id_false_reject_rate
from ood_u import contract
from ood_u.data import SplitRecords
from ood_u.model import ADAMRV11Net, predict_logits


def class_indices(records: SplitRecords) -> np.ndarray:
    """Map known-class modulation names to 0..11 (ID records only)."""
    if records.family != "id":
        raise ValueError("class_indices requires ID records")
    lookup = {name: i for i, name in enumerate(contract.LABEL_ORDER_12)}
    return np.asarray([lookup[str(m)] for m in records.modulation], dtype=np.int64)


def logits_for(model: ADAMRV11Net, records: SplitRecords, *, batch: int = 256) -> np.ndarray:
    planar = records.planar
    parts = [predict_logits(model, planar[i:i + batch]) for i in range(0, len(planar), batch)]
    if not parts:
        return np.empty((0, contract.OUTPUT_DIM), dtype=np.float64)
    return np.concatenate(parts, axis=0)


def _ranking(id_scores: np.ndarray, ood_scores: np.ndarray,
             id_correct: np.ndarray) -> dict[str, float]:
    return {
        "auroc": auroc(id_scores, ood_scores),
        "aupr_in": aupr_in(id_scores, ood_scores),
        "aupr_out": aupr_out(id_scores, ood_scores),
        "fpr95": fpr95(id_scores, ood_scores),
        "oscr_auc": float(oscr(id_scores, ood_scores, id_correct)["auc_ccr_fpr"]),
    }


def _score_method(id_logits: np.ndarray, near_logits: np.ndarray, far_logits: np.ndarray,
                  amb_logits: np.ndarray, impaired_logits: np.ndarray,
                  id_correct: np.ndarray, method: str, temperature: float) -> dict[str, Any]:
    id_s = compute_scores(id_logits, method, temperature)
    near_s = compute_scores(near_logits, method, temperature)
    far_s = compute_scores(far_logits, method, temperature)
    amb_s = compute_scores(amb_logits, method, temperature)
    impaired_s = compute_scores(impaired_logits, method, temperature)
    overall_s = np.concatenate([near_s, far_s])

    t99 = float(np.quantile(id_s, 0.99)) if len(id_s) else float("nan")
    result: dict[str, Any] = {
        "method": method,
        "temperature": temperature,
        "near": _ranking(id_s, near_s, id_correct),
        "far": _ranking(id_s, far_s, id_correct),
        "overall": _ranking(id_s, overall_s, id_correct),
        "ambiguous_side_report": _ranking(id_s, amb_s, id_correct),
        "id_frr_at_99pct": id_false_reject_rate(id_s, t99),
        "impaired_id_accept_at_99pct": float(np.mean(impaired_s <= t99)) if len(impaired_s) else float("nan"),
        "threshold_99pct": t99,
    }
    return result


def run_score_benchmark(
    model: ADAMRV11Net,
    id_val: SplitRecords,
    near_val: SplitRecords,
    far_val: SplitRecords,
    amb_val: SplitRecords,
    impaired_id_val: SplitRecords,
    *,
    temperature: float = 1.0,
) -> dict[str, Any]:
    """Run all five methods and return a per-method report keyed by method name."""
    id_logits = logits_for(model, id_val)
    near_logits = logits_for(model, near_val)
    far_logits = logits_for(model, far_val)
    amb_logits = logits_for(model, amb_val)
    impaired_logits = logits_for(model, impaired_id_val)
    id_correct = (np.argmax(id_logits, axis=1) == class_indices(id_val))

    methods: dict[str, Any] = {}
    for method in contract.SCORE_METHODS:
        methods[method] = _score_method(
            id_logits, near_logits, far_logits, amb_logits, impaired_logits,
            id_correct, method, temperature,
        )
    return {
        "id_samples": len(id_val),
        "near_samples": len(near_val),
        "far_samples": len(far_val),
        "ambiguous_samples": len(amb_val),
        "impaired_id_samples": len(impaired_id_val),
        "temperature": temperature,
        "methods": methods,
    }


__all__ = ["class_indices", "logits_for", "run_score_benchmark"]
