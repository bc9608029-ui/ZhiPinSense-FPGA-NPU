"""Select 24-class pilot candidates to promote to formal (validation-only).

Deduplicates pilot trials by canonical candidate signature *before* ranking:
trials that sampled an identical training-affecting config collapse to their best
trial, duplicates are reported, then the unique configs are ranked on the frozen
selection metric ``rated_0_20_accuracy`` and the top ``top_candidates`` are
promoted.  The default promotes exactly ONE candidate; a second candidate is
promoted only with ``--allow-second-candidate`` AND an explicit better-in-a-key-
dimension justification, keeping the default formal budget at 3 runs
(1 candidate x 3 seeds).

Outputs (under the pilot root's parent):
  * ``pilot_unique_candidates.json`` — deduplicated, ranked, promoted candidates;
  * ``pilot_duplicate_report.json`` — duplicate groups and their kept trial.
"""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any

from training.utils import load_yaml, save_json
from v2.candidate_signature import canonical_candidate_signature, load_artifact_shas
from v2.results import collect_trial_results, prune, rank, selection_score

_QAM_INDICES = (12, 13, 14, 15, 16)  # 16QAM..256QAM in the frozen 24-class order
_SCORE_DELTA_TOL = 0.01
_DIM_TOL = 1e-4


def apply_candidate(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct the full training config for a candidate (base + v2/training)."""
    cfg = copy.deepcopy(base)
    cfg["v2"] = dict(candidate.get("v2", {}))
    cfg.setdefault("training", {}).update(candidate.get("training", {}))
    return cfg


def _baseline_metrics(result: dict[str, Any]) -> dict[str, Any]:
    return (result.get("baseline") or {}).get("metrics") or {}


def _worst_class_recall(result: dict[str, Any]) -> float:
    return float(_baseline_metrics(result).get("min_per_class_accuracy", 0.0))


def _low_snr_accuracy(result: dict[str, Any]) -> float:
    return float(_baseline_metrics(result).get("snr_0_accuracy", 0.0))


def _min_qam_recall(result: dict[str, Any]) -> float:
    per_class = _baseline_metrics(result).get("per_class_accuracy") or []
    values = [float(per_class[i]) for i in _QAM_INDICES if i < len(per_class)]
    return min(values) if values else 0.0


# Key dimensions the second candidate must beat the first in (>=1) to be promoted.
# fake-INT8 / semantic-OOD dimensions are formal-only and are NOT available at
# pilot/select time; they are noted here and re-verified by the formal gate.
_KEY_DIMS = (
    ("worst_class_recall", _worst_class_recall),
    ("low_snr_accuracy", _low_snr_accuracy),
    ("min_qam_recall", _min_qam_recall),
)


def _dedupe(results: list[dict[str, Any]], base: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        signature = canonical_candidate_signature(apply_candidate(base, result))
        groups.setdefault(signature, []).append(result)

    unique: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for signature, group in groups.items():
        group = sorted(group, key=selection_score, reverse=True)
        best = group[0]
        unique.append(best)
        if len(group) > 1:
            duplicates.append({
                "candidate_signature": signature,
                "kept_trial": best.get("trial"),
                "duplicate_trials": [r.get("trial") for r in group[1:]],
                "reason": (
                    "identical training-affecting config "
                    "(same model/loss/optimizer/lr/wd/scheduler/...)"
                ),
            })
    return unique, duplicates


def _second_candidate_qualifies(first: dict[str, Any], second: dict[str, Any]) -> tuple[bool, str]:
    score_delta = abs(selection_score(first) - selection_score(second))
    if score_delta > _SCORE_DELTA_TOL:
        return False, f"score_delta={score_delta:.4f} > {_SCORE_DELTA_TOL}"
    better = [name for name, fn in _KEY_DIMS if fn(second) > fn(first) + _DIM_TOL]
    if not better:
        return False, "not better in any key dimension (worst_class_recall/low_snr/min_qam)"
    return True, "better_in=" + ",".join(better)


def _candidate_entry(result: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
    return {
        "trial": result.get("trial"),
        "candidate_signature": canonical_candidate_signature(apply_candidate(base, result)),
        "selection_score": float(selection_score(result)),
        "v2": dict(result.get("v2", {})),
        "training": dict(result.get("training", {})),
    }


def select_rml24(config_path: str | Path = "configs/rml24_base.yaml",
                 search_space_path: str | Path = "configs/search_space_rml24.yaml",
                 pilot_root: str | Path | None = None,
                 n_top: int | None = None,
                 output_path: str | Path | None = None,
                 allow_second_candidate: bool = False) -> dict[str, Any]:
    """Dedupe + rank 24-class pilot trials and promote the top candidate(s)."""
    base = load_yaml(config_path)
    search = load_yaml(search_space_path)
    cfg = search.get("search", {})
    n_top = int(n_top if n_top is not None else cfg.get("prune", {}).get("top_candidates", 1))
    if n_top < 1:
        raise ValueError("top_candidates must be >= 1")
    if n_top > 2:
        raise ValueError(
            f"top_candidates={n_top} exceeds the frozen budget cap of 2 candidates "
            f"(6 formal runs); further candidates require explicit authorization"
        )
    seeds = list(cfg.get("formal_seeds", [2026, 2027, 2028]))

    if pilot_root is None:
        pilot_root = f"runs/rml24_base/pilot"
    pilot_root = Path(pilot_root)
    parent = pilot_root.parent

    base = dict(base)
    base.update(load_artifact_shas())

    results = collect_trial_results(pilot_root)
    kept, rejected = prune(results, cfg.get("prune", {}))
    unique, duplicates = _dedupe(kept, base)
    ranked = rank(unique)

    promoted: list[dict[str, Any]]
    second_reason: str
    if n_top == 1 or len(ranked) < 2:
        promoted = ranked[:1]
        second_reason = "second_candidate_not_authorized (default budget is 1 candidate x 3 seeds)"
    elif not allow_second_candidate:
        promoted = ranked[:1]
        second_reason = "second_candidate_rejected: --allow-second-candidate not set"
    else:
        ok, reason = _second_candidate_qualifies(ranked[0], ranked[1])
        if ok:
            promoted = ranked[:2]
            second_reason = "second_candidate_promoted: " + reason
        else:
            promoted = ranked[:1]
            second_reason = "second_candidate_rejected: " + reason

    candidates = [_candidate_entry(r, base) for r in promoted]

    payload: dict[str, Any] = {
        "pilot_root": str(pilot_root),
        "n_trials": len(results),
        "n_kept": len(kept),
        "n_rejected": len(rejected),
        "n_unique": len(unique),
        "n_duplicates": len(duplicates),
        "top_candidates": n_top,
        "n_promoted": len(candidates),
        "formal_seeds": seeds,
        "allow_second_candidate": bool(allow_second_candidate),
        "second_candidate_reason": second_reason,
        "candidates": candidates,
        "ranking": [r["trial"] for r in ranked],
        "rejected": [{"trial": r["trial"], "reasons": r.get("_reject_reasons", [])} for r in rejected],
    }
    save_json(payload, parent / "pilot_unique_candidates.json")
    save_json({"n_duplicates": len(duplicates), "groups": duplicates},
              parent / "pilot_duplicate_report.json")
    # Legacy name kept for compatibility; formal reads pilot_unique_candidates.json.
    save_json({"candidates": candidates}, output_path or parent / "selected_candidates.json")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--search-space", default="configs/search_space_rml24.yaml")
    parser.add_argument("--pilot-root", required=True)
    parser.add_argument("--n-top", type=int, default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--allow-second-candidate", action="store_true")
    args = parser.parse_args()
    payload = select_rml24(args.config, args.search_space, args.pilot_root, args.n_top,
                           args.output, args.allow_second_candidate)
    print(f"select done: n_unique={payload['n_unique']} n_promoted={payload['n_promoted']} "
          f"seeds={payload['formal_seeds']}")


if __name__ == "__main__":
    main()
