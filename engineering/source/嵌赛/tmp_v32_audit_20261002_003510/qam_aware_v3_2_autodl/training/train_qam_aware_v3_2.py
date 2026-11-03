"""Train the frozen-V2-preserving QAM-Aware RFNet V3.2.

At initialization the V3.2 backbone is loaded *strictly* from the frozen V2
champion checkpoint, its scalar gate is zero, and its logits are verified to be
element-wise equal to V2's before any optimizer step.  A separate frozen V2
teacher then provides soft targets for knowledge distillation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from models.qam_aware_rfnet import build_qam_aware_model
from models.qam_aware_rfnet_v3_2 import (
    build_qam_aware_v3_2,
    load_v2_into_v3_2,
    qam_aware_v3_2_profile,
)
from training.qam_aware_v3_2_trainer import QAMAwareV32Trainer
from training.qam_aware_v3_2_utils import load_qam_aware_v3_2_config
from training.utils import ensure_output_dirs, environment_info, git_commit, set_seed, select_device


def _loader(dataset: SyntheticModulationDataset, config: dict, device: torch.device, *, train: bool) -> DataLoader:
    workers = int(config["dataset"].get("num_workers", 0))
    options = {
        "batch_size": int(config["training"]["batch_size"]),
        "num_workers": workers,
        "pin_memory": device.type == "cuda",
        "persistent_workers": False,
    }
    generator = torch.Generator().manual_seed(int(config["seed"])) if train else None
    return DataLoader(dataset, shuffle=train, generator=generator, **options)


def _build_v2_teacher(checkpoint: dict, num_classes: int, device: torch.device) -> torch.nn.Module:
    qam_aware = checkpoint["config"]["qam_aware"]
    teacher = build_qam_aware_model(variant="time_power_phase", num_classes=num_classes, **qam_aware)
    teacher.load_state_dict(checkpoint["model_state"], strict=True)
    teacher.to(device).eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    return teacher


@torch.inference_mode()
def _verify_init_matches_v2(
    model: torch.nn.Module,
    teacher: torch.nn.Module,
    device: torch.device,
    sample_length: int,
) -> float:
    """Guarantee the zero-gate initialization reproduces V2 element-wise."""

    if float(model.core.gate.item()) != 0.0:
        raise RuntimeError("V3.2 gate must be exactly zero at initialization.")
    # Compare in eval mode so dropout is off and BatchNorm uses running stats,
    # matching the frozen teacher.  (A train-mode comparison would diff because
    # the student's dropout/BN batch stats are active.)
    was_training = model.training
    model.eval()
    torch.manual_seed(0)
    iq = torch.randn(8, 2, int(sample_length), device=device)
    diff = (model(iq) - teacher(iq)).abs().max().item()
    model.train(was_training)
    if diff > 1e-5:
        raise RuntimeError(f"Initial V3.2 logits differ from V2 by {diff}; expected element-wise equality.")
    return diff


@torch.inference_mode()
def _finite_probe(model: torch.nn.Module, loader: DataLoader, device: torch.device) -> dict[str, object]:
    inputs, labels = next(iter(loader))[:2]
    logits = model(inputs.to(device))
    return {
        "input_shape": list(inputs.shape),
        "label_shape": list(labels.shape),
        "logit_shape": list(logits.shape),
        "finite_logits": bool(torch.isfinite(logits).all().item()),
    }


def train_v3_2(
    config_path: str,
    resume: str | None = None,
    stop_after_epoch: int | None = None,
) -> list[dict[str, float]]:
    config = load_qam_aware_v3_2_config(config_path)
    epochs = int(config["training"]["epochs"])
    if not 1 <= epochs <= 200:
        raise RuntimeError("V3.2 epochs must be in [1, 200]")
    seed = int(config["seed"])
    set_seed(seed)
    device = select_device(str(config.get("device", "auto")))
    paths = ensure_output_dirs(config["output_root"])
    classes = [str(name).upper() for name in config["signal"]["modulations"]]
    snrs = [float(value) for value in config["dataset"]["snr_values"]]
    sample_length = int(config["signal"]["sample_length"])

    v2_checkpoint = torch.load(config["v2_checkpoint"], map_location="cpu", weights_only=False)
    model = build_qam_aware_v3_2(len(classes), **config["model"])
    load_v2_into_v3_2(model, v2_checkpoint)
    teacher = _build_v2_teacher(v2_checkpoint, len(classes), device)
    init_diff = _verify_init_matches_v2(model.to(device), teacher, device, sample_length)

    train_set = SyntheticModulationDataset(
        int(config["dataset"]["train_samples"]),
        config["signal"],
        config["channel"],
        seed,
        "v3_2_train",
        snr_values=snrs,
    )
    val_set = SyntheticModulationDataset(
        int(config["dataset"]["val_samples"]),
        config["signal"],
        config["channel"],
        seed,
        "v3_2_validation",
        snr_values=snrs,
    )
    train_loader = _loader(train_set, config, device, train=True)
    val_loader = _loader(val_set, config, device, train=False)

    profile = qam_aware_v3_2_profile(model, sample_length)
    (paths["tables"] / "model_profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
    effective = {key: value for key, value in config.items() if not key.startswith("_")}
    config_dir = paths["checkpoints"].parent / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "effective_config.json").write_text(json.dumps(effective, indent=2), encoding="utf-8")

    snapshot = {
        "track": "qam_aware_v3_2",
        "experiment_config": config["_experiment_path"],
        "requested_config": config["_requested_config_path"],
        "baseline_config": config["_baseline_path"],
        "git_commit": git_commit(),
        "seed": seed,
        "device": str(device),
        "classes": classes,
        "final_blind_test_accessed": False,
        "v2_checkpoint": config["v2_checkpoint"],
        "init_logits_match_v2": True,
        "init_logits_max_abs_diff": init_diff,
        "init_gate": float(model.core.gate.item()),
        "distillation": config["training"].get("distillation", {}),
        "model_profile": profile,
        "environment": environment_info(),
    }
    (paths["logs"] / "experiment_snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    trainer = QAMAwareV32Trainer(model, device, config, paths, classes, teacher=teacher)
    history = trainer.fit(
        train_loader,
        val_loader,
        resume_path=resume,
        stop_after_epoch=stop_after_epoch,
    )
    best_path = paths["checkpoints"] / "best.pt"
    best = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(best["model_state"])
    model.to(device).eval()
    probe = _finite_probe(model, val_loader, device)
    if not probe["finite_logits"]:
        raise RuntimeError("Reloaded V3.2 checkpoint produced NaN/Inf logits")

    manifest = {
        **snapshot,
        "epochs_completed": len(history),
        "best_epoch": int(best["epoch"]),
        "best_metrics": best["metrics"],
        "training_time_sec": trainer.total_training_time_sec,
        "peak_process_rss_mb": trainer.peak_rss_mb,
        "amp_enabled": trainer.amp_enabled,
        "checkpoint_reload_ok": True,
        "final_gate": float(model.core.gate.item()),
        "validation_probe": probe,
    }
    (paths["logs"] / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return history


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_2_smoke.yaml")
    parser.add_argument("--resume", default=None)
    parser.add_argument("--stop-after-epoch", type=int, default=None)
    args = parser.parse_args()
    train_v3_2(args.config, resume=args.resume, stop_after_epoch=args.stop_after_epoch)


if __name__ == "__main__":
    main()
