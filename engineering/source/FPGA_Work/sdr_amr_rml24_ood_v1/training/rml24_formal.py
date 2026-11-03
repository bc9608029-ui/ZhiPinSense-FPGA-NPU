"""24-class formal training: full-budget, multi-seed runs of selected candidates.

Runs each promoted candidate across the frozen formal seeds, writes per-seed
``result.json``, and produces a per-candidate ``multi_seed_summary.json``.  Unlike
the pilot, the formal run also computes the fake-INT8 and channel-covariate OOD
axes.  Selection stays validation-only; the test split is never touched here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from training.rml24_run import run_rml24_trial
from training.utils import load_yaml, save_json
from v2.results import collect_trial_results, multi_seed_summary, write_summary_table


def _apply(base: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    import copy
    cfg = copy.deepcopy(base)
    cfg["v2"] = dict(candidate.get("v2", {}))
    cfg.setdefault("training", {}).update(candidate.get("training", {}))
    return cfg


def run_rml24_formal(config_path: str | Path, search_space_path: str | Path,
                     candidates_path: str | Path, output_root: str | Path | None = None,
                     seeds: list[int] | None = None,
                     ood_domains: list[str] | None = None) -> dict[str, Any]:
    base = load_yaml(config_path)
    search = load_yaml(search_space_path)
    cfg = search.get("search", {})
    seeds = list(seeds or cfg.get("formal_seeds", [3407, 2026, 39]))
    epochs = int(cfg.get("formal_epochs", base["training"]["epochs"]))
    candidates = json.loads(Path(candidates_path).read_text(encoding="utf-8")).get("candidates", [])
    if not candidates:
        raise RuntimeError(f"no candidates in {candidates_path}")

    root = Path(output_root or base["output_root"]) / "formal"
    root.mkdir(parents=True, exist_ok=True)
    summaries: dict[str, Any] = {}
    for candidate in candidates:
        name = str(candidate["trial"])
        cand_root = root / name
        for seed in seeds:
            run_rml24_trial(_apply(base, candidate), f"seed{seed}", cand_root,
                            seed=seed, epochs=epochs, eval_baseline=True,
                            eval_fake_int8=True, eval_channel_ood=True,
                            ood_domains=ood_domains)
            print(f"formal {name} seed{seed} done", flush=True)
        seed_results = collect_trial_results(cand_root)
        summaries[name] = multi_seed_summary(seed_results)

    save_json({"seeds": seeds, "epochs": epochs, "candidates": summaries},
              root / "formal_summary.json")
    write_summary_table([r for name in summaries for r in collect_trial_results(root / name)],
                        root / "formal_summary.csv")
    return {"output_root": str(root), "n_candidates": len(candidates), "seeds": seeds}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--search-space", default="configs/search_space_rml24.yaml")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--seeds", type=int, nargs="+", default=None)
    args = parser.parse_args()
    print(run_rml24_formal(args.config, args.search_space, args.candidates,
                           args.output_root, args.seeds))


if __name__ == "__main__":
    main()
