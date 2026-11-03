"""V2 result aggregation, pruning, ranking, and multi-seed statistics.

Selection is performed ONLY on validation metrics (never the final holdout /
real-RF / deployment golden splits).  The declared selection metric is the
baseline validation ``rated_0_20_accuracy``; OOD drops are tracked for the
acceptance gates but never used to re-expand the frozen search space.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SELECTION_METRIC = "rated_0_20_accuracy"
SELECTION_BELOW = 0.55
TOP_CANDIDATES = 3

_KEY_METRICS = (
    "accuracy", "macro_f1", "rated_0_20_accuracy", "high_10_20_accuracy",
    "snr_0_accuracy", "min_per_class_accuracy",
)


def selection_score(result: dict[str, Any]) -> float:
    baseline = result.get("baseline") or {}
    metrics = baseline.get("metrics") or {}
    return float(metrics.get(SELECTION_METRIC, 0.0))


def collect_trial_results(trials_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(trials_dir)
    results: list[dict[str, Any]] = []
    for path in sorted(root.rglob("result.json")):
        try:
            results.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"corrupt result.json at {path}: {exc}")
    return results


def _has_nan_inf(result: dict[str, Any]) -> bool:
    history = result.get("history") or []
    for row in history:
        for value in row.values():
            if isinstance(value, float):
                if value != value or value in (float("inf"), float("-inf")):
                    return True
    return False


def prune(results: list[dict[str, Any]], prune_cfg: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = prune_cfg or {}
    below = float(cfg.get("selection_metric_below", SELECTION_BELOW))
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for result in results:
        reasons: list[str] = []
        if _has_nan_inf(result):
            reasons.append("nan_inf_any")
        history = result.get("history") or []
        if not history:
            reasons.append("no_convergence")
        score = selection_score(result)
        if score < below:
            reasons.append(f"selection_metric_below:{score:.4f}")
        if reasons:
            result["_reject_reasons"] = reasons
            rejected.append(result)
        else:
            kept.append(result)
    return kept, rejected


def rank(results: list[dict[str, Any]], metric: str = SELECTION_METRIC) -> list[dict[str, Any]]:
    return sorted(results, key=selection_score, reverse=True)


def select_top(results: list[dict[str, Any]], n: int = TOP_CANDIDATES) -> list[dict[str, Any]]:
    kept, _ = prune(results)
    return rank(kept)[:n]


def _mean_std(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": float("nan"), "std": float("nan"), "min": float("nan"), "max": float("nan")}
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return {"mean": mean, "std": variance ** 0.5, "min": min(values), "max": max(values)}


def multi_seed_summary(seed_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-seed trial results into mean/std/min/max per metric."""
    per_metric: dict[str, list[float]] = {key: [] for key in _KEY_METRICS}
    ood_drops: dict[str, list[float]] = {}
    for result in seed_results:
        baseline = (result.get("baseline") or {}).get("metrics") or {}
        for key in _KEY_METRICS:
            value = baseline.get(key)
            per_metric[key].append(float(value) if value is not None else float("nan"))
        for domain, ood in (result.get("ood") or {}).items():
            ood_metrics = (ood.get("metrics") or {})
            baseline_value = float(baseline.get("accuracy", 0.0))
            ood_value = float(ood_metrics.get("accuracy", 0.0))
            ood_drops.setdefault(domain, []).append(baseline_value - ood_value)
    summary: dict[str, Any] = {
        "num_seeds": len(seed_results),
        "selection_metric": {key: _mean_std(per_metric[key]) for key in _KEY_METRICS},
        "ood_accuracy_drop": {domain: _mean_std(drops) for domain, drops in ood_drops.items()},
    }
    return summary


def per_snr_curve(result: dict[str, Any]) -> dict[str, float]:
    """Extract the baseline per-SNR accuracy curve (SNR label -> accuracy)."""
    metrics = (result.get("baseline") or {}).get("metrics") or {}
    per_snr = metrics.get("per_snr_accuracy") or {}
    return {str(k): float(v) for k, v in per_snr.items()}


def confusion_matrix(result: dict[str, Any]) -> list[list[int]]:
    metrics = (result.get("baseline") or {}).get("metrics") or {}
    return metrics.get("confusion_matrix") or []


def write_summary_table(results: list[dict[str, Any]], out_path: str | Path,
                        classes: list[str] | None = None) -> None:
    """Write a deterministic CSV of trial names and key metrics."""
    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    header = ["trial", "seed", "phase", SELECTION_METRIC, "accuracy", "macro_f1",
              "snr_0_accuracy", "min_per_class_accuracy", "best_epoch"]
    rows = [header]
    for result in sorted(results, key=lambda r: (r.get("phase", ""), r.get("trial", ""))):
        baseline = (result.get("baseline") or {}).get("metrics") or {}
        rows.append([
            str(result.get("trial", "")),
            str(result.get("seed", "")),
            str(result.get("phase", "")),
            f"{selection_score(result):.6f}",
            f"{float(baseline.get('accuracy', 0.0)):.6f}",
            f"{float(baseline.get('macro_f1', 0.0)):.6f}",
            f"{float(baseline.get('snr_0_accuracy', 0.0)):.6f}",
            f"{float(baseline.get('min_per_class_accuracy', 0.0)):.6f}",
            str(result.get("best_epoch", "")),
        ])
    destination.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")
