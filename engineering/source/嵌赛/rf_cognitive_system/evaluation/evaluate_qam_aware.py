"""Smoke-only evaluation and QAM confusion diagnostics for QAM-Aware V2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from evaluation.evaluate import predict
from models.qam_aware_rfnet import build_qam_aware_model
from training.metrics import classification_metrics
from training.qam_aware_utils import load_qam_aware_config
from training.utils import ensure_output_dirs, select_device, set_seed


def _qam_metrics(targets: np.ndarray, predictions: np.ndarray, classes: list[str]) -> dict[str, float | int]:
    targets = np.asarray(targets, dtype=np.int64)
    predictions = np.asarray(predictions, dtype=np.int64)
    q16, q64 = classes.index("16QAM"), classes.index("64QAM")
    mask16, mask64 = targets == q16, targets == q64
    count16, count64 = int(mask16.sum()), int(mask64.sum())
    confused_16_to_64 = int(((predictions == q64) & mask16).sum())
    confused_64_to_16 = int(((predictions == q16) & mask64).sum())
    return {
        "16qam_samples": count16,
        "64qam_samples": count64,
        "16qam_accuracy": float(((predictions == q16) & mask16).sum() / count16),
        "64qam_accuracy": float(((predictions == q64) & mask64).sum() / count64),
        "16qam_to_64qam_count": confused_16_to_64,
        "64qam_to_16qam_count": confused_64_to_16,
        "16qam_to_64qam_rate": float(confused_16_to_64 / count16),
        "64qam_to_16qam_rate": float(confused_64_to_16 / count64),
    }


def evaluate_smoke_variant(config_path: str, variant: str) -> dict[str, object]:
    config = load_qam_aware_config(config_path)
    if int(config["training"]["epochs"]) > 2:
        raise RuntimeError("This evaluator is guarded for QAM-Aware smoke runs only.")
    set_seed(int(config["seed"]))
    device = select_device(config.get("device", "auto"))
    paths = ensure_output_dirs(str(Path(config["output_root"]) / variant))
    checkpoint = torch.load(paths["checkpoints"] / "best.pt", map_location=device, weights_only=False)
    classes = list(checkpoint["class_names"])
    model = build_qam_aware_model(variant, len(classes), **config["qam_aware"]).to(device).eval()
    model.load_state_dict(checkpoint["model_state"])

    current_test = SyntheticModulationDataset(
        config["dataset"]["test_samples"], config["signal"], config["channel"], int(config["seed"]),
        "test", snr_values=config["dataset"]["snr_values"]
    )
    loader = DataLoader(current_test, batch_size=int(config["evaluation"]["batch_size"]), shuffle=False)
    probe_inputs, _ = next(iter(loader))
    with torch.inference_mode():
        probe_logits = model(probe_inputs.to(device))
    finite_logits = bool(torch.isfinite(probe_logits).all().item())
    if not finite_logits:
        raise RuntimeError("Smoke evaluation produced NaN/Inf logits")
    targets, predictions = predict(model, loader, device)
    overall = classification_metrics(targets, predictions, len(classes))
    overall.pop("confusion_matrix")

    by_snr: dict[str, object] = {}
    count = int(config["evaluation"]["samples_per_modulation_per_snr"])
    for snr in config["evaluation"]["snr_values"]:
        dataset = SyntheticModulationDataset(
            count * len(classes), config["signal"], config["channel"], int(config["seed"]),
            f"snr_sweep_{snr}", fixed_snr_db=float(snr)
        )
        snr_loader = DataLoader(dataset, batch_size=int(config["evaluation"]["batch_size"]), shuffle=False)
        snr_targets, snr_predictions = predict(model, snr_loader, device)
        by_snr[str(snr)] = _qam_metrics(snr_targets, snr_predictions, classes)

    report = {
        "scope": "smoke/current frozen test namespace only; final_blind_test was not accessed",
        "variant": variant,
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "overall_accuracy": float(overall["accuracy"]),
        "macro_f1": float(overall["macro_f1"]),
        "overall_qam": _qam_metrics(targets, predictions, classes),
        "qam_by_snr": by_snr,
        "finite_logits_and_pipeline": finite_logits,
    }
    (paths["tables"] / "smoke_evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v2_smoke.yaml")
    parser.add_argument("--variant", required=True, choices=("time_power", "time_phase", "time_power_phase"))
    args = parser.parse_args()
    print(json.dumps(evaluate_smoke_variant(args.config, args.variant), indent=2))


if __name__ == "__main__":
    main()
