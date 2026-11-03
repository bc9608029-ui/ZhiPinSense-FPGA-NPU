"""Train one Time/Frequency/Dual ablation without changing the frozen data contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from models.dual_domain_rfnet import ablation_model_profile, build_ablation_model
from training.ablation_utils import load_ablation_config
from training.resumable_trainer import ResumableTrainer
from training.utils import ensure_output_dirs, environment_info, git_commit, set_seed, select_device


def train_variant(config_path: str, variant: str, resume: str | None = None) -> list[dict[str, float]]:
    config = load_ablation_config(config_path)
    if variant not in config["variants"]:
        raise ValueError(f"Variant {variant} is not enabled by {config['_experiment_path']}")
    seed = int(config["seed"])
    set_seed(seed)
    device = select_device(config.get("device", "auto"))
    output_dir = str(Path(config["output_root"]) / variant)
    config["output_dir"] = output_dir
    paths = ensure_output_dirs(output_dir)
    classes = list(config["signal"]["modulations"])
    snrs = config["dataset"].get("snr_values")
    train_set = SyntheticModulationDataset(config["dataset"]["train_samples"], config["signal"], config["channel"], seed, "train", snr_values=snrs)
    val_set = SyntheticModulationDataset(config["dataset"]["val_samples"], config["signal"], config["channel"], seed, "validation", snr_values=snrs)
    options = {
        "batch_size": int(config["training"]["batch_size"]),
        "num_workers": int(config["dataset"].get("num_workers", 0)),
        "pin_memory": device.type == "cuda",
    }
    generator = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(train_set, shuffle=True, generator=generator, **options)
    val_loader = DataLoader(val_set, shuffle=False, **options)
    model = build_ablation_model(variant, len(classes), **config["dual_domain"])
    profile = ablation_model_profile(model, int(config["signal"]["sample_length"]))
    (paths["tables"] / "model_profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
    snapshot = {
        "experiment_config": config["_experiment_path"],
        "baseline_config": config["_config_path"],
        "baseline_git_commit": "2bd657983c062582450b8da871f87df9345264d6",
        "current_git_commit": git_commit(),
        "variant": variant,
        "seed": seed,
        "model": config["dual_domain"],
    }
    (paths["logs"] / "experiment_snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"variant={variant} device={device} profile={json.dumps(profile)}")
    trainer = ResumableTrainer(model, device, config, paths, classes)
    history = trainer.fit(train_loader, val_loader, resume_path=resume)
    manifest = {
        **snapshot,
        "environment": environment_info(),
        "epochs_completed": len(history),
        "best_epoch": trainer.best_epoch,
        "training_time_sec": trainer.total_training_time_sec,
        "peak_process_rss_mb": trainer.peak_rss_mb,
        "model_profile": profile,
        "resume": trainer.resume_metadata,
    }
    (paths["logs"] / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return history


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/dual_domain_v1.yaml")
    parser.add_argument("--variant", required=True, choices=("time_only", "frequency_only", "time_only_wide", "dual"))
    parser.add_argument("--resume", default=None, help="Path to a complete or migratable last.pt checkpoint")
    args = parser.parse_args()
    train_variant(args.config, args.variant, resume=args.resume)


if __name__ == "__main__":
    main()
