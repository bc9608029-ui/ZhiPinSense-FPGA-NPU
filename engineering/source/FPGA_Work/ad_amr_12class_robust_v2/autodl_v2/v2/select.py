"""Select pilot candidates to promote to formal (validation-only, no test/leak)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from training.utils import load_yaml, save_json
from v2.results import collect_trial_results, prune, rank, select_top


def _training_overrides(result: dict[str, Any]) -> dict[str, Any]:
    training = result.get("training") or {}
    return {
        "learning_rate": training.get("learning_rate"),
        "weight_decay": training.get("weight_decay"),
    }


def select(config_path: str | Path, search_space_path: str | Path,
           pilot_root: str | Path, n_top: int | None = None,
           output_path: str | Path | None = None) -> dict[str, Any]:
    base = load_yaml(config_path)
    search = load_yaml(search_space_path)
    cfg = search.get("search", {})
    n_top = int(n_top or search.get("prune", {}).get("top_candidates", 3))

    results = collect_trial_results(pilot_root)
    kept, rejected = prune(results, search.get("prune", {}))
    top = select_top(results, n_top)
    candidates = [
        {"trial": r["trial"], "v2": r.get("v2", {}),
         "training": _training_overrides(r),
         "selection_score": r.get("best_selection_score")}
        for r in top
    ]

    payload: dict[str, Any] = {
        "pilot_root": str(pilot_root),
        "n_trials": len(results),
        "n_kept": len(kept),
        "n_rejected": len(rejected),
        "rejected": [{"trial": r["trial"], "reasons": r.get("_reject_reasons", [])} for r in rejected],
        "candidates": candidates,
        "ranking": [r["trial"] for r in rank(kept)],
    }
    destination = Path(output_path or Path(pilot_root).parent / "selected_candidates.json")
    save_json(payload, destination)
    return payload


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/v2_base.yaml")
    parser.add_argument("--search-space", default="configs/search_space_v2.yaml")
    parser.add_argument("--pilot-root", required=True)
    parser.add_argument("--n-top", type=int, default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    print(select(args.config, args.search_space, args.pilot_root, args.n_top, args.output))


if __name__ == "__main__":
    main()
