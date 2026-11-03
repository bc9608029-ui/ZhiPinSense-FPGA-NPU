"""V2 hyperparameter pilot (Phase A/B) — optuna, with a seeded fallback.

Search space is frozen in ``configs/search_space_v2.yaml``.  Trials are trained
with a small epoch budget, evaluated on the *validation* split only, and written
to ``<output_root>/pilot/seed<pilot_seed>/<trial>/result.json``.

The declared method is ``optuna`` (TPE sampler over the discrete axes).  If
``optuna`` is unavailable the same axes are sampled with a seeded NumPy
generator so the pilot still runs reproducibly.  The scheduler axis is fixed to
V1's ReduceLROnPlateau in this increment (cosine annealing declared, not wired).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np

from training.utils import load_yaml, save_json
from v2.results import collect_trial_results, rank, selection_score, write_summary_table
from v2.run import run_trial

CURRICULA = ("none", "very_low_first", "linear_warmup")
AUG_GROUPS = ((), ("A",), ("B",), ("C",), ("D",),
              ("A", "C"), ("A", "B", "C"), ("A", "B", "C", "D"))
LOSSES = ("cross_entropy", "focal", "label_smoothing", "class_balanced")
CLASS_SAMPLING = ("balanced", "class_balanced", "hard_example_16qam_64qam")
OPTIMIZERS = ("adamw", "sgd")
FOCUS_OOD_DOMAINS = ["cfo_strong", "multipath", "multi_impairment"]


def _choice(rng: np.random.Generator, values: tuple) -> Any:
    return values[int(rng.integers(0, len(values)))]


def sample_v2(rng: np.random.Generator) -> dict[str, Any]:
    v2: dict[str, Any] = {}
    v2["snr_curriculum"] = _choice(rng, CURRICULA)
    v2["augmentation_groups"] = list(_choice(rng, AUG_GROUPS))
    loss = _choice(rng, LOSSES)
    v2["loss"] = loss
    if loss == "focal":
        v2["focal_gamma"] = float(_choice(rng, (1.0, 2.0, 3.0)))
    if loss == "label_smoothing":
        v2["label_smoothing"] = float(_choice(rng, (0.05, 0.1)))
    v2["class_sampling"] = _choice(rng, CLASS_SAMPLING)
    v2["optimizer"] = _choice(rng, OPTIMIZERS)
    return v2


def sample_training(rng: np.random.Generator, v2: dict[str, Any]) -> dict[str, Any]:
    training: dict[str, Any] = {}
    if v2["optimizer"] == "adamw":
        training["learning_rate"] = float(_choice(rng, (1e-3, 3e-4, 1e-4)))
        training["weight_decay"] = float(_choice(rng, (1e-4, 1e-5)))
    else:
        training["learning_rate"] = float(_choice(rng, (1e-2, 3e-3)))
        training["weight_decay"] = float(_choice(rng, (1e-4,)))
    return training


def sample_v2_optuna(trial: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    v2: dict[str, Any] = {}
    v2["snr_curriculum"] = trial.suggest_categorical("snr_curriculum", list(CURRICULA))
    v2["augmentation_groups"] = trial.suggest_categorical(
        "augmentation_groups", [list(g) for g in AUG_GROUPS])
    loss = trial.suggest_categorical("loss", list(LOSSES))
    v2["loss"] = loss
    if loss == "focal":
        v2["focal_gamma"] = trial.suggest_categorical("focal_gamma", [1.0, 2.0, 3.0])
    if loss == "label_smoothing":
        v2["label_smoothing"] = trial.suggest_categorical("label_smoothing", [0.05, 0.1])
    v2["class_sampling"] = trial.suggest_categorical("class_sampling", list(CLASS_SAMPLING))
    v2["optimizer"] = trial.suggest_categorical("optimizer", list(OPTIMIZERS))
    training: dict[str, Any] = {}
    if v2["optimizer"] == "adamw":
        training["learning_rate"] = trial.suggest_categorical("lr", [1e-3, 3e-4, 1e-4])
        training["weight_decay"] = trial.suggest_categorical("wd", [1e-4, 1e-5])
    else:
        training["learning_rate"] = trial.suggest_categorical("lr", [1e-2, 3e-3])
        training["weight_decay"] = trial.suggest_categorical("wd", [1e-4])
    return v2, training


def trial_name(index: int, v2: dict[str, Any]) -> str:
    aug = "".join(v2.get("augmentation_groups", [])) or "base"
    return f"t{index:03d}_aug{aug}_cur{v2.get('snr_curriculum', 'none')}" \
           f"_loss{v2.get('loss', 'ce')}_opt{v2.get('optimizer', 'adamw')}"


def apply_trial(base: dict[str, Any], v2: dict[str, Any], training: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base)
    cfg["v2"] = dict(v2)
    cfg.setdefault("training", {}).update(training)
    return cfg


def _finalize(root: Path, completed: list[dict[str, Any]], seed: int, epochs: int) -> dict[str, Any]:
    ranked = rank(completed)
    save_json({"seed": seed, "epochs": epochs, "n_trials": len(completed),
               "results": completed, "ranking": [r["trial"] for r in ranked]},
              root / "pilot_summary.json")
    write_summary_table(completed, root / "pilot_summary.csv")
    return {"output_root": str(root), "n_trials": len(completed), "results": completed}


def run_pilot(config_path: str | Path, search_space_path: str | Path,
              n_trials: int | None = None, output_root: str | Path | None = None) -> dict[str, Any]:
    base = load_yaml(config_path)
    search = load_yaml(search_space_path)
    cfg = search.get("search", {})
    seed = int(cfg.get("pilot_seed", 2026))
    epochs = int(cfg.get("pilot_epochs", 30))
    n_trials = int(n_trials or cfg.get("n_pilot_trials", 24))
    root = Path(output_root or base["output_root"]) / "pilot" / f"seed{seed}"
    root.mkdir(parents=True, exist_ok=True)

    try:
        import optuna  # type: ignore
    except ImportError:
        optuna = None  # type: ignore

    completed: list[dict[str, Any]] = []
    if optuna is not None:
        def objective(trial: Any) -> float:
            v2, training = sample_v2_optuna(trial)
            name = trial_name(int(trial.number), v2)
            result = run_trial(apply_trial(base, v2, training), name, root,
                               seed=seed, epochs=epochs, ood_domains=FOCUS_OOD_DOMAINS)
            completed.append(result)
            print(f"pilot trial {name}: rated_0_20={selection_score(result):.4f}", flush=True)
            return selection_score(result)

        study = optuna.create_study(direction="maximize",
                                    sampler=optuna.samplers.TPESampler(seed=seed))
        study.optimize(objective, n_trials=n_trials)
        return _finalize(root, completed, seed, epochs)

    rng = np.random.default_rng(seed)
    for index in range(n_trials):
        v2 = sample_v2(rng)
        training = sample_training(rng, v2)
        name = trial_name(index, v2)
        result = run_trial(apply_trial(base, v2, training), name, root,
                           seed=seed, epochs=epochs, ood_domains=FOCUS_OOD_DOMAINS)
        completed.append(result)
        print(f"pilot trial {name}: rated_0_20={selection_score(result):.4f}", flush=True)
    return _finalize(root, completed, seed, epochs)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/v2_base.yaml")
    parser.add_argument("--search-space", default="configs/search_space_v2.yaml")
    parser.add_argument("--n-trials", type=int, default=None)
    parser.add_argument("--output-root", default=None)
    args = parser.parse_args()
    summary = run_pilot(args.config, args.search_space, args.n_trials, args.output_root)
    print(f"pilot done: {summary['output_root']} ({summary['n_trials']} trials)")


if __name__ == "__main__":
    main()
