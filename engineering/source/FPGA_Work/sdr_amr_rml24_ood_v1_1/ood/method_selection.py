"""Validation-only OOD score-method selection (MSP / Entropy / MaxLogit / Energy).

The calibration report stores, per method, the full ranking metrics computed on
``ood_validation``.  This module turns those metrics into a *deterministic*
recommendation over the four score methods, and gates the threshold freeze on the
recommended method carrying complete, finite validation metrics.

The selection is a pure function of the calibration metrics only.  There is no
code path here that reads a final report (``test`` / ``ood_final_test``) or any
file at all, so the recommendation cannot be steered by final data.  The ranking
rule is a Borda count over five criteria — **not AUROC alone** — AUROC,
FPR@95%TPR, OSCR, ID false-reject rate and OOD reject rate.
"""

from __future__ import annotations

from typing import Any

import numpy as np

WORKING_POINTS = ("conservative", "balanced", "strict")

# (criteria key in ``_extract_criteria``, display label, higher-is-better)
SELECTION_CRITERIA = (
    ("auroc", "AUROC", True),
    ("fpr95", "FPR@95TPR", False),
    ("oscr", "OSCR", True),
    ("id_frr", "ID false-reject rate", False),
    ("ood_reject", "OOD reject rate", True),
)


def _get(node: dict[str, Any], path: str) -> Any:
    obj: Any = node
    for part in path.split("."):
        if not isinstance(obj, dict) or part not in obj:
            raise KeyError(path)
        obj = obj[part]
    return obj


def _finite(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} is not a finite number: {value!r}") from None
    if not np.isfinite(number):
        raise ValueError(f"{label} is non-finite: {value!r}")
    return number


def _require_finite(node: dict[str, Any], path: str, label: str) -> float:
    try:
        value = _get(node, path)
    except KeyError:
        raise ValueError(f"{label} is missing (expected at {path!r})") from None
    return _finite(value, label)


def require_complete_method_metrics(families: dict[str, Any], method: str,
                                    *, target_operating_point: str = "balanced") -> None:
    """Fail-closed check that ``method`` carries complete, finite validation metrics.

    Covers every quantity the calibration report is required to produce per method:
    the three frozen working points (with ID FRR / accept rate and OOD FAR / reject
    rate), the ranking metrics (AUROC / AUPR-IN / AUPR-OUT / FPR@95TPR), the
    bootstrap 95% CIs, and the OSCR.  Any missing or non-finite field raises.
    """
    if method not in families:
        raise ValueError(f"score method {method!r} is missing from the calibration report")
    node = families[method]
    if not isinstance(node, dict):
        raise ValueError(f"calibration metrics for {method!r} must be a mapping")

    thresholds = node.get("thresholds")
    if not isinstance(thresholds, dict) or tuple(sorted(thresholds)) != tuple(sorted(WORKING_POINTS)):
        raise ValueError(f"{method}: thresholds must carry conservative/balanced/strict")
    for name in WORKING_POINTS:
        spec = thresholds.get(name)
        if not isinstance(spec, dict):
            raise ValueError(f"{method}: thresholds[{name!r}] is missing")
        _finite(spec.get("threshold"), f"{method}.thresholds.{name}.threshold")
        _finite(spec.get("id_frr"), f"{method}.thresholds.{name}.id_frr")
        _finite(spec.get("ood_far"), f"{method}.thresholds.{name}.ood_far")

    for key in ("auroc", "aupr_in", "aupr_out", "fpr95"):
        _require_finite(node, f"ranking.{key}", f"{method}.ranking.{key}")

    for ci in ("auroc_ci", "fpr95_ci"):
        for stat in ("estimate", "lower", "upper"):
            _require_finite(node, f"{ci}.{stat}", f"{method}.{ci}.{stat}")

    _require_finite(node, "oscr.auc_ccr_fpr", f"{method}.oscr.auc_ccr_fpr")

    if target_operating_point not in WORKING_POINTS:
        raise ValueError(f"target_operating_point {target_operating_point!r} not in {WORKING_POINTS}")
    for key in ("threshold", "id_frr", "id_accept_rate", "ood_far", "ood_rejected_fraction"):
        _require_finite(node, f"working_points.{target_operating_point}.{key}",
                        f"{method}.working_points.{target_operating_point}.{key}")


def _extract_criteria(node: dict[str, Any], target_operating_point: str) -> dict[str, float]:
    wp = node["working_points"][target_operating_point]
    return {
        "auroc": float(node["ranking"]["auroc"]),
        "fpr95": float(node["ranking"]["fpr95"]),
        "oscr": float(node["oscr"]["auc_ccr_fpr"]),
        "id_frr": float(wp["id_frr"]),
        "ood_reject": float(wp["ood_rejected_fraction"]),
    }


def _build_rationale(ranked: list[str], totals: dict[str, float]) -> str:
    winner = ranked[0]
    runner = ranked[1] if len(ranked) > 1 else None
    parts = [
        f"{winner} is recommended by a validation-only Borda count over "
        f"{len(SELECTION_CRITERIA)} criteria (AUROC, FPR@95TPR, OSCR, ID false-reject, OOD reject).",
    ]
    if runner is not None:
        parts.append(f"Runner-up is {runner} (Borda {totals[runner]:g} vs {totals[winner]:g}).")
    parts.append("Selection uses calibration data only; final results are not consulted.")
    return " ".join(parts)


def select_score_method(families: dict[str, Any], *,
                        target_operating_point: str = "balanced") -> dict[str, Any]:
    """Deterministically rank the four score methods on calibration metrics.

    Returns ``recommended_score_method`` plus the full ranking and a rationale.
    Fails closed (``ValueError``) if any method lacks complete, finite validation
    metrics, so the recommendation can never be produced from a partial comparison.
    """
    if not isinstance(families, dict) or not families:
        raise ValueError("families must be a non-empty mapping of method -> metrics")
    methods = sorted(families)
    for method in methods:
        require_complete_method_metrics(families, method,
                                        target_operating_point=target_operating_point)

    values = {m: _extract_criteria(families[m], target_operating_point) for m in methods}

    totals: dict[str, float] = {m: 0.0 for m in methods}
    for key, _label, higher_better in SELECTION_CRITERIA:
        order = sorted(methods, key=lambda m: values[m][key], reverse=bool(higher_better))
        for pos, m in enumerate(order):
            totals[m] += len(methods) - 1 - pos

    ranked = sorted(methods, key=lambda m: (-totals[m], m))
    recommended = ranked[0]
    return {
        "recommended_score_method": recommended,
        "selection_rule": "borda_count_over_auroc_fpr95_oscr_id_frr_ood_reject",
        "target_operating_point": target_operating_point,
        "validation_only": True,
        "final_data_used": False,
        "criteria": [{"name": label, "higher_is_better": bool(hb)}
                     for _key, label, hb in SELECTION_CRITERIA],
        "ranking": [
            {"method": m, "borda": totals[m], "criteria": values[m]} for m in ranked
        ],
        "rationale": _build_rationale(ranked, totals),
    }


def build_method_selection_evidence(recommendation: dict[str, Any],
                                    score_method: str) -> dict[str, Any]:
    """Summarise the method-selection decision for the frozen threshold manifest."""
    return {
        "selection_rule": recommendation["selection_rule"],
        "target_operating_point": recommendation["target_operating_point"],
        "validation_only": True,
        "final_data_used": False,
        "recommended_score_method": recommendation["recommended_score_method"],
        "frozen_score_method": score_method,
        "frozen_score_method_matches_recommended":
            score_method == recommendation["recommended_score_method"],
        "criteria": recommendation["criteria"],
        "ranking": recommendation["ranking"],
        "rationale": recommendation["rationale"],
    }


__all__ = [
    "WORKING_POINTS",
    "SELECTION_CRITERIA",
    "select_score_method",
    "require_complete_method_metrics",
    "build_method_selection_evidence",
]
