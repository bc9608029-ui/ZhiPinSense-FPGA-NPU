"""At-most-two-epoch development smoke trainer for QAM-Aware RFNet V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import numpy as np
from sklearn.metrics import confusion_matrix, f1_score
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from models.qam_aware_rfnet import build_qam_aware_model, qam_aware_model_profile
from training.qam_aware_utils import load_qam_aware_config
from training.resumable_trainer import ResumableTrainer
from training.utils import ensure_output_dirs, environment_info, git_commit, set_seed, select_device


@torch.inference_mode()
def _validation_diagnostic(
    model: torch.nn.Module, loader: DataLoader, device: torch.device, classes: list[str]
) -> dict[str, object]:
    targets: list[int] = []
    predictions: list[int] = []
    model.eval()
    for inputs, labels in loader:
        logits = model(inputs.to(device))
        if not torch.isfinite(logits).all():
            raise RuntimeError("Validation produced NaN/Inf logits")
        targets.extend(labels.tolist())
        predictions.extend(logits.argmax(dim=1).cpu().tolist())
    target_array = np.asarray(targets)
    prediction_array = np.asarray(predictions)
    matrix = confusion_matrix(target_array, prediction_array, labels=np.arange(len(classes)))
    per_class_f1 = f1_score(
        target_array, prediction_array, labels=np.arange(len(classes)), average=None, zero_division=0
    )
    q16, q64 = classes.index("16QAM"), classes.index("64QAM")
    return {
        "scope": "fixed validation split only; no development_test or final blind records",
        "samples": len(targets),
        "per_class_f1": dict(zip(classes, per_class_f1.tolist())),
        "16qam_accuracy": float(matrix[q16, q16] / matrix[q16].sum()),
        "64qam_accuracy": float(matrix[q64, q64] / matrix[q64].sum()),
        "16qam_to_64qam_rate": float(matrix[q16, q64] / matrix[q16].sum()),
        "64qam_to_16qam_rate": float(matrix[q64, q16] / matrix[q64].sum()),
    }


def train_qam_variant(config_path: str, variant: str, resume: str | None = None) -> list[dict[str, float]]:
    config = load_qam_aware_config(config_path)
    epochs = int(config["training"]["epochs"])
    if epochs not in {2, 40}:
        raise RuntimeError("QAM-Aware V2 protocol guard: only 2-epoch smoke or frozen 40-epoch formal runs are allowed.")
    if variant not in config["variants"]:
        raise ValueError(f"Variant {variant} is not enabled")

    seed = int(config["seed"])
    set_seed(seed)
    device = select_device(config.get("device", "auto"))
    output_dir = str(Path(config["output_root"]) / variant)
    config["output_dir"] = output_dir
    paths = ensure_output_dirs(output_dir)
    config_dir = paths["checkpoints"].parent / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    classes = list(config["signal"]["modulations"])
    snrs = config["dataset"]["snr_values"]
    train_set = SyntheticModulationDataset(
        config["dataset"]["train_samples"], config["signal"], config["channel"], seed, "train", snr_values=snrs
    )
    val_set = SyntheticModulationDataset(
        config["dataset"]["val_samples"], config["signal"], config["channel"], seed, "validation", snr_values=snrs
    )
    loader_options = {
        "batch_size": int(config["training"]["batch_size"]),
        "num_workers": int(config["dataset"].get("num_workers", 0)),
        "pin_memory": device.type == "cuda",
    }
    train_generator = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(train_set, shuffle=True, generator=train_generator, **loader_options)
    val_loader = DataLoader(val_set, shuffle=False, **loader_options)
    model = build_qam_aware_model(variant, len(classes), **config["qam_aware"])
    profile = qam_aware_model_profile(model, int(config["signal"]["sample_length"]))
    (paths["tables"] / "model_profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
    snapshot = {
        "experiment_config": config["_experiment_path"],
        "run_config": config["_requested_config_path"],
        "baseline_config": config["_config_path"],
        "git_commit": git_commit(),
        "variant": variant,
        "seed": seed,
        "model": config["qam_aware"],
        "smoke_only": epochs == 2,
        "formal_protocol": epochs == 40,
    }
    (paths["logs"] / "experiment_snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    effective = {key: value for key, value in config.items() if not key.startswith("_")}
    (config_dir / "effective_config.json").write_text(json.dumps(effective, indent=2), encoding="utf-8")
    environment = environment_info()
    (paths["logs"] / "environment.json").write_text(json.dumps(environment, indent=2), encoding="utf-8")
    trainer = ResumableTrainer(model, device, config, paths, classes)
    history = trainer.fit(train_loader, val_loader, resume_path=resume)

    checkpoint = torch.load(paths["checkpoints"] / "last.pt", map_location="cpu", weights_only=False)
    reloaded = build_qam_aware_model(variant, len(classes), **config["qam_aware"])
    reloaded.load_state_dict(checkpoint["model_state"])
    finite = all(torch.isfinite(tensor).all().item() for tensor in checkpoint["model_state"].values())
    best_checkpoint = torch.load(paths["checkpoints"] / "best.pt", map_location=device, weights_only=False)
    model.load_state_dict(best_checkpoint["model_state"])
    validation_diagnostic = _validation_diagnostic(model, val_loader, device, classes)
    (paths["tables"] / "validation_qam_diagnostic.json").write_text(
        json.dumps(validation_diagnostic, indent=2), encoding="utf-8"
    )
    manifest = {
        **snapshot,
        "environment": environment,
        "epochs_completed": len(history),
        "best_epoch": trainer.best_epoch,
        "training_time_sec": trainer.total_training_time_sec,
        "peak_process_rss_mb": trainer.peak_rss_mb,
        "loss_decreased": bool(history[-1]["train_loss"] < history[0]["train_loss"]),
        "checkpoint_reload_ok": True,
        "finite_checkpoint": bool(finite),
        "validation_qam_diagnostic": validation_diagnostic,
        "model_profile": profile,
    }
    (paths["logs"] / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return history


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v2_smoke.yaml")
    parser.add_argument("--variant", required=True, choices=("time_power", "time_phase", "time_power_phase"))
    parser.add_argument("--resume", default=None)
    args = parser.parse_args()
    train_qam_variant(args.config, args.variant, resume=args.resume)


if __name__ == "__main__":
    main()
