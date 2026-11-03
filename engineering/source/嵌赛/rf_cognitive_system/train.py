"""Train the compact baseline CNN from a YAML configuration."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from models.baseline_cnn import BaselineCNN, model_profile
from training.trainer import Trainer
from training.utils import ensure_output_dirs, environment_info, git_commit, load_config, select_device, set_seed


def run_training(config_path: str) -> list[dict[str, float]]:
    config = load_config(config_path)
    seed = int(config["seed"])
    set_seed(seed)
    device = select_device(config.get("device", "auto"))
    paths = ensure_output_dirs(config["output_dir"])
    class_names = list(config["signal"]["modulations"])
    stratified_snrs = config["dataset"].get("snr_values")
    train_set = SyntheticModulationDataset(
        config["dataset"]["train_samples"], config["signal"], config["channel"], seed=seed, split="train", snr_values=stratified_snrs
    )
    val_set = SyntheticModulationDataset(
        config["dataset"]["val_samples"], config["signal"], config["channel"], seed=seed, split="validation", snr_values=stratified_snrs
    )
    generator = torch.Generator().manual_seed(seed)
    loader_options = {
        "batch_size": int(config["training"]["batch_size"]),
        "num_workers": int(config["dataset"].get("num_workers", 0)),
        "pin_memory": device.type == "cuda",
    }
    train_loader = DataLoader(train_set, shuffle=True, generator=generator, **loader_options)
    val_loader = DataLoader(val_set, shuffle=False, **loader_options)
    model = BaselineCNN(len(class_names), **config["model"])
    profile = model_profile(model, int(config["signal"]["sample_length"]))
    (paths["tables"] / "model_profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
    config_source = Path(config["_config_path"]).read_text(encoding="utf-8")
    (paths["logs"] / "config_snapshot.yaml").write_text(config_source, encoding="utf-8")
    print(f"device={device} profile={json.dumps(profile)}")
    started_at = datetime.now(timezone.utc).isoformat()
    trainer = Trainer(model, device, config, paths, class_names)
    history = trainer.fit(train_loader, val_loader)
    manifest = {
        "seed": seed,
        "config_file": config["_config_path"],
        "git_commit": git_commit(),
        "environment": environment_info(),
        "selected_device": str(device),
        "model_profile": profile,
        "epochs_completed": len(history),
        "best_epoch": trainer.best_epoch,
        "training_time_sec": trainer.total_training_time_sec,
        "peak_process_rss_mb": trainer.peak_rss_mb,
        "started_at_utc": started_at,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (paths["logs"] / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return history


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/baseline.yaml")
    args = parser.parse_args()
    run_training(args.config)


if __name__ == "__main__":
    main()
