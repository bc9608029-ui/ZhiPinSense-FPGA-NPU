"""Train + evaluate a single V2 trial (shared by pilot and formal)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from datasets.ad_amr_dataset import collate_ad_amr
from training.utils import ensure_output_dirs, load_yaml, save_json, select_device, set_seed
from v2.contract import V1_MODEL_SHA, V2_MODEL_NAME
from v2.evaluate import evaluate_ood, evaluate_v1_1
from v2.fake_int8 import fake_int8_report
from v2.trainer import V2Trainer, build_v2_train_dataset


def _build_loaders(config: dict[str, Any], device: torch.device) -> tuple[DataLoader, DataLoader]:
    train_ds = build_v2_train_dataset(config, "train")
    val_ds = build_v2_train_dataset(config, "val")
    batch_size = int(config["training"]["batch_size"])
    num_workers = int(config["dataset"].get("num_workers", 0))
    pin = device.type == "cuda"
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True,
                              num_workers=num_workers, collate_fn=collate_ad_amr,
                              pin_memory=pin, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False,
                            num_workers=num_workers, collate_fn=collate_ad_amr,
                            pin_memory=pin, drop_last=False)
    return train_loader, val_loader


def run_trial(config: dict[str, Any] | str, trial_name: str, output_root: str | Path,
              seed: int, epochs: int, eval_ood: bool = True,
              eval_fake_int8: bool = True, ood_domains: list[str] | None = None,
              classes: list[str] | None = None) -> dict[str, Any]:
    """Train one trial, evaluate, and write ``result.json`` under output_root/trial_name."""
    cfg = copy.deepcopy(config) if isinstance(config, dict) else load_yaml(config)
    cfg["seed"] = int(seed)
    cfg["output_root"] = str(Path(output_root) / trial_name)
    cfg["training"] = dict(cfg.get("training", {}))
    cfg["training"]["epochs"] = int(epochs)
    if cfg["training"].get("minimum_epochs_before_stopping", 30) > int(epochs):
        cfg["training"]["minimum_epochs_before_stopping"] = int(epochs)

    label_order = classes or [str(v).upper() for v in cfg["signal"]["modulations"]]
    set_seed(int(seed))

    device = select_device(str(cfg.get("device", "auto")))

    train_loader, val_loader = _build_loaders(cfg, device)
    paths = ensure_output_dirs(cfg["output_root"])

    trainer = V2Trainer(cfg, paths, label_order)
    trainer.fit(train_loader, val_loader)
    trainer.save_summary()

    best_path = paths["checkpoints"] / "best.pt"
    result: dict[str, Any] = {
        "trial": trial_name,
        "seed": int(seed),
        "epochs": int(epochs),
        "model_name": V2_MODEL_NAME,
        "v1_model_sha": V1_MODEL_SHA,
        "v2": cfg.get("v2", {}),
        "best_epoch": trainer.best_epoch,
        "best_selection_score": float(trainer.best_score),
        "history": trainer.history,
        "checkpoint_path": str(best_path),
        "training": dict(cfg["training"]),
    }

    if eval_ood:
        result["baseline"] = evaluate_v1_1(cfg, best_path)
        result["ood"] = evaluate_ood(cfg, best_path, domains=ood_domains)
    if eval_fake_int8:
        result["fake_int8"] = fake_int8_report(cfg, best_path)

    save_json(result, paths["logs"] / "result.json")
    return result
