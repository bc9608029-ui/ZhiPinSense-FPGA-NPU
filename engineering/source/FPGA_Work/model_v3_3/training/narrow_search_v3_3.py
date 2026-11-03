"""Budget-controlled narrow hyperparameter search for the V3.3 residual expert.

After the A0-A3 ablation names a winning *mechanism* (and that trained winner
clears the preliminary improvement threshold), a *narrow* random search tunes only
the expert's own knobs — expert learning rate, residual bound, residual penalty,
family auxiliary weight and numeric/domain consistency weight — on the **two fixed
validation seeds** plus synthetic OOD.  The development test and final blind
namespaces are never instantiated, so the search can never leak test data.

The search is budget-controlled in both dimensions the mandate cares about:

* ``max_trials`` caps the number of sampled configurations (8);
* ``epochs_per_trial`` caps how far each trial trains before it is scored (6).

The best sampled configuration is then **re-confirmed at the full ablation epoch
count (15) on both seeds** with validation + OOD, and returned as a candidate
record (same shape as an ablation variant) so the orchestrator can freeze it into
``selected_candidate.yaml``/``.json`` — it is never a reference-only side output.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import shutil
from pathlib import Path

import yaml

from evaluation.evaluate_qam_aware_v3_3 import evaluate_v3_3_validation
from evaluation.evaluate_qam_aware_v3_3_ood import evaluate_v3_3_ood
from training.qam_aware_v3_3_utils import write_text_lf
from training.train_qam_aware_v3_3 import train_v3_3
from training.utils import PROJECT_ROOT, resolve_project_path
from training.v3_3_split_guard import enter_selection_scope, exit_selection_scope, FORBIDDEN_SPLITS

# (name, low, high, log_scale) — the five tunable expert knobs.
SEARCH_SPACE = {
    "learning_rate": (0.0003, 0.003, True),
    "residual_bound": (0.5, 2.0, False),
    "residual_penalty_weight": (0.0, 0.05, False),
    "family_aux_loss_weight": (0.0, 1.0, False),
    "domain_consistency_weight": (0.0, 1.0, False),
}


def _sample_point(space: dict, rng: random.Random) -> dict[str, float]:
    point: dict[str, float] = {}
    for name, (low, high, log_scale) in space.items():
        if log_scale:
            point[name] = math.exp(rng.uniform(math.log(low), math.log(high)))
        else:
            point[name] = rng.uniform(low, high)
    return point


def _apply_point(base_model: dict, base_training: dict, point: dict[str, float]) -> tuple[dict, dict]:
    model = copy.deepcopy(base_model)
    training = copy.deepcopy(base_training)
    model.setdefault("residual_expert", {})["residual_bound"] = float(point["residual_bound"])
    training["learning_rate"] = float(point["learning_rate"])
    training["residual_penalty_weight"] = float(point["residual_penalty_weight"])
    training["family_aux_loss_weight"] = float(point["family_aux_loss_weight"])
    training.setdefault("domain_consistency", {})["weight"] = float(point["domain_consistency_weight"])
    return model, training


def _read_yaml(path: str) -> dict:
    data = yaml.safe_load(resolve_project_path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping: {path}")
    return data


def _full_seed_record(config_path: str, seed: int) -> dict:
    """Evaluate a trained checkpoint with validation + OOD, in the stage1 seed-record shape."""
    report = evaluate_v3_3_validation(config_path, seed=seed)
    summary = report["validation"]
    gap = report["fpga_sim_gap"]
    record = {
        "accuracy": float(summary["accuracy"]),
        "macro_f1": float(summary["macro_f1"]),
        "qam_mean_accuracy": float(summary["qam_mean_accuracy"]),
        "per_class_accuracy": {name: float(value) for name, value in summary["per_class_accuracy"].items()},
        "fpga_sim_accuracy_gap": float(gap.get("accuracy_gap", 0.0)),
        "fpga_sim_macro_f1_gap": float(gap.get("macro_f1_gap", 0.0)),
    }
    ood = evaluate_v3_3_ood(config_path, seed=seed)
    record["ood"] = {"worst_domain_macro_f1": float(ood["worst_domain_macro_f1"]), "domains": ood["domains"]}
    return record


def _build_search_space(search: dict) -> dict:
    space = dict(SEARCH_SPACE)
    if isinstance(search.get("space"), dict):
        for name, bounds in search["space"].items():
            if name in space and isinstance(bounds, list) and len(bounds) == 2:
                space[name] = (float(bounds[0]), float(bounds[1]), space[name][2])
    return space


def run_narrow_search(
    stage1_path: str,
    *,
    winner_variant: str,
    winner_model: dict,
    winner_training: dict,
) -> dict | None:
    """Run the narrow search on the *actual Stage-1 winning mechanism*.

    Returns a candidate record (same shape as an ablation variant, named
    ``<winner>_tuned``) whose best configuration has been re-confirmed at the full
    ablation epoch count on both selection seeds with validation + OOD.  Returns
    ``None`` when the search is disabled.
    """

    spec = _read_yaml(stage1_path)
    search = dict(spec.get("narrow_search", {}) or {})
    if not search.get("enabled", False):
        return None

    base_experiment = spec["experiment_config"]
    ablation_root = resolve_project_path(spec["output_root"])
    root = ablation_root / "narrow_search"
    seeds = [int(seed) for seed in spec["selection_seeds"]]
    max_trials = int(search.get("max_trials", 8))
    epochs_per_trial = int(search.get("epochs_per_trial", 6))
    full_epochs = int(spec["ablation_epochs"])
    rng = random.Random(int(search.get("random_seed", 2026)))

    space = _build_search_space(search)
    base_model = dict(winner_model)
    base_training = dict(winner_training)

    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    enter_selection_scope()
    try:
        trials: list[dict] = []
        for trial_index in range(max_trials):
            point = _sample_point(space, rng)
            seed_scores: list[float] = []
            trial_dir = root / f"trial{trial_index:03d}"
            for seed in seeds:
                model_cfg, training_cfg = _apply_point(base_model, base_training, point)
                training_cfg["epochs"] = epochs_per_trial
                override = {
                    "experiment_config": base_experiment,
                    "seed": seed,
                    "output_root": (trial_dir / f"seed{seed}").relative_to(PROJECT_ROOT).as_posix(),
                    "model": model_cfg,
                    "training": training_cfg,
                }
                config_file = trial_dir / f"seed{seed}_config.yaml"
                write_text_lf(config_file, yaml.safe_dump(override, sort_keys=False))
                train_v3_3(str(config_file), stop_after_epoch=epochs_per_trial)
                report = evaluate_v3_3_validation(str(config_file), seed=seed)
                seed_scores.append(float(report["validation"]["macro_f1"]))

            score = sum(seed_scores) / len(seed_scores)
            trials.append({"trial": trial_index, "point": point, "seed_macro_f1": seed_scores, "mean_macro_f1": score})

        trials.sort(key=lambda item: -item["mean_macro_f1"])
        best = trials[0] if trials else None

        candidate = None
        if best is not None:
            best_model, best_training = _apply_point(base_model, base_training, best["point"])
            seed_records: dict[str, dict] = {}
            best_dir = root / "best"
            for seed in seeds:
                override = {
                    "experiment_config": base_experiment,
                    "seed": seed,
                    "output_root": (best_dir / f"seed{seed}").relative_to(PROJECT_ROOT).as_posix(),
                    "model": best_model,
                    "training": best_training,
                }
                config_file = best_dir / f"seed{seed}_config.yaml"
                write_text_lf(config_file, yaml.safe_dump(override, sort_keys=False))
                train_v3_3(str(config_file), stop_after_epoch=full_epochs)
                seed_records[str(seed)] = _full_seed_record(str(config_file), seed)
            candidate = {
                "variant": f"{winner_variant}_tuned",
                "trained": True,
                "tuned": True,
                "base_variant": winner_variant,
                "seeds": seed_records,
                "model": best_model,
                "training": best_training,
                "best_point": best["point"],
                "mean_macro_f1": best["mean_macro_f1"],
            }
    finally:
        accessed = exit_selection_scope()

    forbidden_accessed = [split for split in accessed if split in FORBIDDEN_SPLITS]
    result = {
        "enabled": True,
        "winner_variant": winner_variant,
        "base_experiment": base_experiment,
        "selection_seeds": seeds,
        "max_trials": max_trials,
        "epochs_per_trial": epochs_per_trial,
        "full_epochs": full_epochs,
        "search_space": {name: list(bounds) for name, bounds in space.items()},
        "best": best,
        "trials": trials,
        "forbidden_splits_accessed": forbidden_accessed,
        "candidate_variant": candidate["variant"] if candidate else None,
    }
    write_text_lf(root / "narrow_search_result.json", json.dumps(result, indent=2) + "\n")
    if candidate is not None:
        write_text_lf(
            root / "narrow_search_best.yaml",
            yaml.safe_dump({"model": candidate["model"], "training": candidate["training"]}, sort_keys=False),
        )
    if forbidden_accessed:
        raise RuntimeError(f"narrow_search accessed forbidden splits {forbidden_accessed}")
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_3_stage1.yaml")
    parser.add_argument("--winner-variant", required=True)
    parser.add_argument("--winner-model", required=True)
    parser.add_argument("--winner-training", required=True)
    args = parser.parse_args()
    candidate = run_narrow_search(
        args.config,
        winner_variant=args.winner_variant,
        winner_model=json.loads(args.winner_model),
        winner_training=json.loads(args.winner_training),
    )
    print(json.dumps(candidate if candidate else {"enabled": False}, indent=2))


if __name__ == "__main__":
    main()
