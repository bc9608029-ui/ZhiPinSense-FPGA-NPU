"""Bounded 24-class hyperparameter pilot (Optuna TPE, with a seeded fallback).

The search space is frozen in ``configs/search_space_rml24.yaml`` and samples only
the discrete loss / optimizer / learning-rate / weight-decay / focal-gamma /
label-smoothing axes (RadioML is a received signal, so there are no synthetic
augmentation or curriculum axes).  Trials run a small epoch budget, are ranked on
the validation ``rated_0_20_accuracy``, and land under
``<output_root>/pilot/seed<pilot_seed>/<trial>/result.json``.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np

from training.rml24_run import run_rml24_trial
from training.utils import load_yaml, save_json
from v2.results import rank, selection_score, write_summary_table

_LOSSES = ("cross_entropy", "focal", "label_smoothing", "class_balanced")
_OPTIMIZERS = ("adamw", "sgd")
_LR_ADAMW = (1.0e-3, 3.0e-4, 1.0e-4)
_WD_ADAMW = (1.0e-4, 1.0e-5)
_LR_SGD = (1.0e-2, 3.0e-3)
_FOCAL_GAMMAS = (1.0, 2.0, 3.0)
_LABEL_SMOOTHINGS = (0.05, 0.1)


def _choice(rng: np.random.Generator, values: tuple) -> Any:
    return values[int(rng.integers(0, len(values)))]


def _build_hyperparams(loss: str, optimizer: str, focal_gamma: Any,
                       label_smoothing: Any, learning_rate: float,
                       weight_decay: float) -> tuple[dict[str, Any], dict[str, Any]]:
    v2: dict[str, Any] = {"loss": loss, "optimizer": optimizer, "class_sampling": "balanced"}
    if loss == "focal":
        v2["focal_gamma"] = float(focal_gamma)
    if loss == "label_smoothing":
        v2["label_smoothing"] = float(label_smoothing)
    training: dict[str, Any] = {"learning_rate": float(learning_rate),
                                "weight_decay": float(weight_decay)}
    return v2, training


def sample_rml24(rng: np.random.Generator) -> tuple[dict[str, Any], dict[str, Any]]:
    loss = _choice(rng, _LOSSES)
    optimizer = _choice(rng, _OPTIMIZERS)
    focal_gamma = _choice(rng, _FOCAL_GAMMAS)
    label_smoothing = _choice(rng, _LABEL_SMOOTHINGS)
    if optimizer == "adamw":
        lr = _choice(rng, _LR_ADAMW)
        wd = _choice(rng, _WD_ADAMW)
    else:
        lr = _choice(rng, _LR_SGD)
        wd = _WD_ADAMW[0]
    return _build_hyperparams(loss, optimizer, focal_gamma, label_smoothing, lr, wd)


def sample_rml24_optuna(trial: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    loss = trial.suggest_categorical("loss", list(_LOSSES))
    optimizer = trial.suggest_categorical("optimizer", list(_OPTIMIZERS))
    focal_gamma = trial.suggest_categorical("focal_gamma", list(_FOCAL_GAMMAS))
    label_smoothing = trial.suggest_categorical("label_smoothing", list(_LABEL_SMOOTHINGS))
    if optimizer == "adamw":
        lr = trial.suggest_categorical("lr", list(_LR_ADAMW))
        wd = trial.suggest_categorical("wd", list(_WD_ADAMW))
    else:
        lr = trial.suggest_categorical("lr", list(_LR_SGD))
        wd = trial.suggest_categorical("wd", [_WD_ADAMW[0]])
    return _build_hyperparams(loss, optimizer, focal_gamma, label_smoothing, lr, wd)


def trial_name(index: int, v2: dict[str, Any]) -> str:
    return f"t{index:03d}_loss{v2.get('loss', 'ce')}_opt{v2.get('optimizer', 'adamw')}"


def apply_rml24_trial(base: dict[str, Any], v2: dict[str, Any],
                      training: dict[str, Any]) -> dict[str, Any]:
    cfg = copy.deepcopy(base)
    cfg["v2"] = dict(v2)
    cfg.setdefault("training", {}).update(training)
    return cfg


def _finalize(root: Path, completed: list[dict[str, Any]], seed: int,
              epochs: int) -> dict[str, Any]:
    ranked = rank(completed)
    save_json({"seed": seed, "epochs": epochs, "n_trials": len(completed),
               "results": completed, "ranking": [r["trial"] for r in ranked]},
              root / "pilot_summary.json")
    write_summary_table(completed, root / "pilot_summary.csv")
    return {"output_root": str(root), "n_trials": len(completed), "results": completed}


def run_rml24_pilot(config_path: str | Path, search_space_path: str | Path,
                    n_trials: int | None = None, output_root: str | Path | None = None,
                    eval_samples: int = 16384) -> dict[str, Any]:
    base = load_yaml(config_path)
    search = load_yaml(search_space_path)
    cfg = search.get("search", {})
    seed = int(cfg.get("pilot_seed", 2026))
    epochs = int(cfg.get("pilot_epochs", 20))
    n_trials = int(n_trials or cfg.get("n_pilot_trials", 12))
    root = Path(output_root or base["output_root"]) / "pilot" / f"seed{seed}"
    root.mkdir(parents=True, exist_ok=True)

    try:
        import optuna  # type: ignore
    except ImportError:
        optuna = None  # type: ignore

    completed: list[dict[str, Any]] = []
    if optuna is not None:
        def objective(trial: Any) -> float:
            v2, training = sample_rml24_optuna(trial)
            name = trial_name(int(trial.number), v2)
            result = run_rml24_trial(apply_rml24_trial(base, v2, training), name, root,
                                     seed=seed, epochs=epochs, eval_baseline=True,
                                     eval_fake_int8=False, eval_channel_ood=False,
                                     eval_samples=eval_samples)
            completed.append(result)
            print(f"pilot trial {name}: rated_0_20={selection_score(result):.4f}", flush=True)
            return selection_score(result)

        study = optuna.create_study(direction="maximize",
                                    sampler=optuna.samplers.TPESampler(seed=seed))
        study.optimize(objective, n_trials=n_trials)
        return _finalize(root, completed, seed, epochs)

    rng = np.random.default_rng(seed)
    for index in range(n_trials):
        v2, training = sample_rml24(rng)
        name = trial_name(index, v2)
        result = run_rml24_trial(apply_rml24_trial(base, v2, training), name, root,
                                 seed=seed, epochs=epochs, eval_baseline=True,
                                 eval_fake_int8=False, eval_channel_ood=False,
                                 eval_samples=eval_samples)
        completed.append(result)
        print(f"pilot trial {name}: rated_0_20={selection_score(result):.4f}", flush=True)
    return _finalize(root, completed, seed, epochs)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--search-space", default="configs/search_space_rml24.yaml")
    parser.add_argument("--n-trials", type=int, default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--eval-samples", type=int, default=16384)
    args = parser.parse_args()
    summary = run_rml24_pilot(args.config, args.search_space, args.n_trials,
                              args.output_root, args.eval_samples)
    print(f"pilot done: {summary['output_root']} ({summary['n_trials']} trials)")


if __name__ == "__main__":
    main()
