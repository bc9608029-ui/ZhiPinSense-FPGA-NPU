"""AD-AMR V1 training entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from datasets.ad_amr_dataset import ADAMRPairDataset, collate_ad_amr
from models.ad_amr_net import build_ad_amr_model, profile_ad_amr_model
from training.ad_amr_trainer import ADAMRTrainer
from training.utils import ensure_output_dirs, load_yaml, save_json, select_device, set_seed


def build_dataloaders(config: dict[str, Any], device: torch.device):
    signal = config["signal"]
    channel = config["channel"]
    seed = int(config["seed"])
    dataset_cfg = config["dataset"]
    snr_values = [float(v) for v in dataset_cfg["snr_values"]]
    batch_size = int(config["training"]["batch_size"])

    train_set = ADAMRPairDataset(
        int(dataset_cfg["train_samples"]), signal, channel, seed, "ad_amr_train", snr_values=snr_values
    )
    val_set = ADAMRPairDataset(
        int(dataset_cfg["val_samples"]), signal, channel, seed, "ad_amr_validation", snr_values=snr_values
    )

    train_loader = DataLoader(
        train_set, batch_size=batch_size, shuffle=True, num_workers=int(dataset_cfg.get("num_workers", 0)),
        collate_fn=collate_ad_amr, generator=torch.Generator().manual_seed(seed), pin_memory=device.type == "cuda",
    )
    val_loader = DataLoader(
        val_set, batch_size=batch_size, shuffle=False, num_workers=int(dataset_cfg.get("num_workers", 0)),
        collate_fn=collate_ad_amr, pin_memory=device.type == "cuda",
    )
    return train_loader, val_loader


def run_training(config: dict[str, Any], resume: bool = False,
                 stop_after_epoch: int | None = None) -> dict[str, Any]:
    seed = int(config["seed"])
    set_seed(seed)
    device = select_device(config.get("device", "auto"))
    classes = [str(name).upper() for name in config["signal"]["modulations"]]
    sample_length = int(config["signal"]["sample_length"])
    paths = ensure_output_dirs(config["output_root"])

    model = build_ad_amr_model(len(classes), **config["model"]).to(device)
    profile = profile_ad_amr_model(model, sample_length)

    train_loader, val_loader = build_dataloaders(config, device)
    trainer = ADAMRTrainer(model, device, config, paths, classes)

    last_path = paths["checkpoints"] / "last.pt"
    if resume and last_path.exists():
        trainer.load_resume(last_path, train_loader)

    history = trainer.fit(train_loader, val_loader, stop_after_epoch=stop_after_epoch)

    best_row = next(
        (row for row in history if int(row["epoch"]) == int(trainer.best_epoch)), None
    )
    best_accuracy = float(best_row["val_accuracy"]) if best_row else float("nan")
    save_json({
        "loss_variant": trainer.loss_variant,
        "seed": seed,
        "best_epoch": trainer.best_epoch,
        "best_validation_macro_f1": trainer.best_metric,
        "best_validation_accuracy": best_accuracy,
        "profile": profile,
        "history": history,
    }, paths["checkpoints"] / "training_summary.json")
    return {"best_epoch": trainer.best_epoch, "best_validation_macro_f1": trainer.best_metric,
            "best_validation_accuracy": best_accuracy, "profile": profile, "history": history}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1.yaml")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    config = load_yaml(args.config)
    result = run_training(config, resume=args.resume)
    print(f"best_epoch={result['best_epoch']} "
          f"best_val_macro_f1={result['best_validation_macro_f1']:.6f} "
          f"params={result['profile']['parameters']}")


if __name__ == "__main__":
    main()
