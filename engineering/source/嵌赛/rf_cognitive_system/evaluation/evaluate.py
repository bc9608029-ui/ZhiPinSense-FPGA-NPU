"""Evaluate a checkpoint on an on-the-fly synthetic test set."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import torch
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from evaluation.confusion_matrix import save_confusion_matrix
from models.baseline_cnn import BaselineCNN
from training.metrics import classification_metrics
from training.utils import ensure_output_dirs, environment_info, git_commit, load_config, select_device, set_seed


@torch.inference_mode()
def predict(model: torch.nn.Module, loader: DataLoader, device: torch.device) -> tuple[list[int], list[int]]:
    model.eval()
    targets: list[int] = []
    predictions: list[int] = []
    for batch in loader:
        inputs, labels = batch[:2]
        logits = model(inputs.to(device))
        targets.extend(labels.tolist())
        predictions.extend(logits.argmax(dim=1).cpu().tolist())
    return targets, predictions


def load_model(config: dict[str, Any], checkpoint_path: Path, device: torch.device) -> tuple[BaselineCNN, list[str]]:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    classes = list(checkpoint.get("class_names", config["signal"]["modulations"]))
    model = BaselineCNN(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"])
    return model.to(device), classes


@torch.inference_mode()
def benchmark_single_sample(model: torch.nn.Module, sample_length: int, device: torch.device, repeats: int = 100) -> float:
    model.eval()
    sample = torch.zeros(1, 2, sample_length, device=device)
    for _ in range(10):
        model(sample)
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    start = time.perf_counter()
    for _ in range(repeats):
        model(sample)
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    return (time.perf_counter() - start) * 1_000.0 / repeats


@torch.inference_mode()
def benchmark_throughput(
    model: torch.nn.Module, sample_length: int, batch_size: int, device: torch.device, repeats: int = 20
) -> float:
    """Measure model-only batch throughput after warm-up."""
    model.eval()
    samples = torch.zeros(batch_size, 2, sample_length, device=device)
    for _ in range(3):
        model(samples)
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    start = time.perf_counter()
    for _ in range(repeats):
        model(samples)
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    return batch_size * repeats / (time.perf_counter() - start)


def evaluate_checkpoint(config: dict[str, Any], checkpoint_path: Path | None = None) -> dict[str, object]:
    set_seed(int(config["seed"]))
    paths = ensure_output_dirs(config["output_dir"])
    device = select_device(config.get("device", "auto"))
    checkpoint_path = checkpoint_path or paths["checkpoints"] / "best.pt"
    model, classes = load_model(config, checkpoint_path, device)
    dataset = SyntheticModulationDataset(
        config["dataset"]["test_samples"],
        config["signal"],
        config["channel"],
        seed=int(config["seed"]),
        split="test",
        snr_values=config["dataset"].get("snr_values"),
    )
    loader = DataLoader(dataset, batch_size=int(config["evaluation"]["batch_size"]), shuffle=False, num_workers=0)
    evaluation_start = time.perf_counter()
    targets, predictions = predict(model, loader, device)
    evaluation_elapsed = time.perf_counter() - evaluation_start
    metrics = classification_metrics(targets, predictions, len(classes))
    matrix = metrics.pop("confusion_matrix")
    save_confusion_matrix(matrix, classes, paths["figures"] / "confusion_matrix.png", paths["tables"] / "confusion_matrix.csv")
    rows = [{"class": name, "accuracy": accuracy} for name, accuracy in zip(classes, metrics["per_class_accuracy"])]
    pd.DataFrame(rows).to_csv(paths["tables"] / "per_class_accuracy.csv", index=False)
    serializable = {
        "overall_accuracy": metrics["accuracy"],
        "macro_f1": metrics["macro_f1"],
        "per_class_accuracy": dict(zip(classes, metrics["per_class_accuracy"])),
        "single_sample_inference_ms": benchmark_single_sample(model, int(config["signal"]["sample_length"]), device),
        "batch_inference_throughput_records_per_sec": benchmark_throughput(
            model,
            int(config["signal"]["sample_length"]),
            int(config["evaluation"]["batch_size"]),
            device,
        ),
        "end_to_end_test_records_per_sec": len(dataset) / evaluation_elapsed,
        "environment": environment_info(),
        "selected_device": str(device),
        "seed": int(config["seed"]),
        "config_file": config["_config_path"],
        "git_commit": git_commit(),
    }
    (paths["tables"] / "test_metrics.json").write_text(json.dumps(serializable, indent=2), encoding="utf-8")
    return serializable


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/baseline.yaml")
    parser.add_argument("--checkpoint", default=None)
    args = parser.parse_args()
    config = load_config(args.config)
    result = evaluate_checkpoint(config, Path(args.checkpoint) if args.checkpoint else None)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
