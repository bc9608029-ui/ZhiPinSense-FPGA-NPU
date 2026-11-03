"""Train + evaluate a single strict 24-class trial (shared by pilot and formal).

Mirrors ``v2.run.run_trial`` but feeds ``RadioML2018Dataset`` through
``RML24Trainer`` instead of the synthetic V2 dataset, and reports the 24-class
closed-set baseline / fake-INT8 / channel-covariate OOD axes (the semantic OOD
baseline is a separate, more expensive step run by ``run_ood_baselines.sh``).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from contracts.rml24_contract import LABEL_ORDER_24, RML24_MODEL_NAME
from evaluation.evaluate_rml24 import (
    evaluate_rml24,
    evaluate_rml24_channel_ood,
    fake_int8_report_rml24,
)
from training.rml24_trainer import RML24Trainer, build_rml24_loader
from training.utils import ensure_output_dirs, load_yaml, save_json, select_device, set_seed


def _eval_samples(cfg: dict[str, Any], key: str, default: int) -> int:
    return int(cfg.get("evaluation", {}).get(key, default))


def run_rml24_trial(config: dict[str, Any] | str, trial_name: str,
                    output_root: str | Path, seed: int, epochs: int, *,
                    classes: list[str] | None = None, eval_baseline: bool = True,
                    eval_fake_int8: bool = True, eval_channel_ood: bool = True,
                    ood_domains: list[str] | None = None,
                    eval_samples: int | None = None, quant_samples: int | None = None,
                    channel_ood_samples: int | None = None,
                    trainer_cls: type[RML24Trainer] = RML24Trainer) -> dict[str, Any]:
    """Train one 24-class trial, evaluate, and write ``result.json`` under output_root/trial_name.

    ``trainer_cls`` lets OE+Energy reuse this path (``OETrainer``) without
    duplicating the loader/eval plumbing.
    """
    cfg = copy.deepcopy(config) if isinstance(config, dict) else load_yaml(config)
    cfg["seed"] = int(seed)
    cfg["output_root"] = str(Path(output_root) / trial_name)
    cfg["training"] = dict(cfg.get("training", {}))
    cfg["training"]["epochs"] = int(epochs)
    if cfg["training"].get("minimum_epochs_before_stopping", 30) > int(epochs):
        cfg["training"]["minimum_epochs_before_stopping"] = int(epochs)

    label_order = list(classes) if classes is not None else list(LABEL_ORDER_24)
    if len(label_order) != len(LABEL_ORDER_24):
        raise ValueError(f"24-class trial requires {len(LABEL_ORDER_24)} classes, got {len(label_order)}")

    set_seed(int(seed))
    device = select_device(str(cfg.get("device", "auto")))

    train_loader = build_rml24_loader(cfg, "train", device, shuffle=True)
    val_loader = build_rml24_loader(cfg, "validation", device, shuffle=False)
    paths = ensure_output_dirs(cfg["output_root"])

    trainer = trainer_cls(cfg, paths, label_order)
    trainer.fit(train_loader, val_loader)
    trainer.save_summary()

    best_path = paths["checkpoints"] / "best.pt"
    model_name = str(cfg.get("rml24", {}).get("model_name", RML24_MODEL_NAME))
    result: dict[str, Any] = {
        "trial": trial_name,
        "seed": int(seed),
        "epochs": int(epochs),
        "model_name": model_name,
        "classes": label_order,
        "best_epoch": trainer.best_epoch,
        "best_selection_score": float(trainer.best_score),
        "history": trainer.history,
        "checkpoint_path": str(best_path),
        "training": dict(cfg["training"]),
        "v2": dict(cfg.get("v2", {})),
    }

    if eval_baseline:
        baseline = evaluate_rml24(cfg, best_path, split="validation", samples=eval_samples)
        result["baseline"] = {
            "metrics": baseline["metrics"], "samples": baseline["samples"],
            "split": baseline["split"], "numeric_mode": baseline["numeric_mode"],
        }
    if eval_fake_int8:
        result["fake_int8"] = fake_int8_report_rml24(
            cfg, best_path, samples=quant_samples or _eval_samples(cfg, "quantization_samples", 16384),
        )
    if eval_channel_ood:
        result["channel_ood"] = evaluate_rml24_channel_ood(
            cfg, best_path, samples=channel_ood_samples or _eval_samples(cfg, "channel_ood_samples", 4096),
            domains=ood_domains,
        )

    save_json(result, paths["logs"] / "result.json")
    return result


__all__ = ["run_rml24_trial"]
