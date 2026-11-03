"""Unified formal development-test evaluation for all frozen QAM-Aware V2 models."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import confusion_matrix, f1_score
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from evaluation.confusion_matrix import save_confusion_matrix
from evaluation.evaluate import benchmark_single_sample, benchmark_throughput
from models.qam_aware_rfnet import build_qam_aware_model
from training.metrics import classification_metrics
from training.qam_aware_utils import load_qam_aware_config
from training.utils import ensure_output_dirs, environment_info, git_commit, select_device, set_seed


@torch.inference_mode()
def _predict_records(
    model: torch.nn.Module, loader: DataLoader, device: torch.device
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    targets, predictions, confidences, logits_parts = [], [], [], []
    model.eval()
    for inputs, labels in loader:
        logits = model(inputs.to(device))
        if not torch.isfinite(logits).all():
            raise RuntimeError("Formal evaluation produced NaN/Inf logits")
        probabilities = torch.softmax(logits, dim=1)
        predicted = logits.argmax(dim=1)
        targets.extend(labels.tolist())
        predictions.extend(predicted.cpu().tolist())
        confidences.extend(probabilities.max(dim=1).values.cpu().tolist())
        logits_parts.append(logits.cpu().numpy())
    return (
        np.asarray(targets, dtype=np.int64),
        np.asarray(predictions, dtype=np.int64),
        np.asarray(confidences, dtype=np.float32),
        np.concatenate(logits_parts, axis=0),
    )


def _per_class_metrics(targets: np.ndarray, predictions: np.ndarray, classes: list[str]) -> pd.DataFrame:
    matrix = confusion_matrix(targets, predictions, labels=np.arange(len(classes)))
    denominators = matrix.sum(axis=1)
    accuracy = np.divide(np.diag(matrix), denominators, out=np.zeros(len(classes)), where=denominators > 0)
    f1 = f1_score(targets, predictions, labels=np.arange(len(classes)), average=None, zero_division=0)
    return pd.DataFrame({"modulation": classes, "accuracy": accuracy, "f1": f1, "samples": denominators})


def _qam_from_matrix(matrix: np.ndarray, classes: list[str]) -> dict[str, float | int]:
    q16, q64 = classes.index("16QAM"), classes.index("64QAM")
    n16, n64 = int(matrix[q16].sum()), int(matrix[q64].sum())
    return {
        "16qam_samples": n16,
        "64qam_samples": n64,
        "16qam_accuracy": float(matrix[q16, q16] / n16),
        "64qam_accuracy": float(matrix[q64, q64] / n64),
        "16qam_to_64qam_count": int(matrix[q16, q64]),
        "64qam_to_16qam_count": int(matrix[q64, q16]),
        "16qam_to_64qam_rate": float(matrix[q16, q64] / n16),
        "64qam_to_16qam_rate": float(matrix[q64, q16] / n64),
    }


def evaluate_variant(config: dict, variant: str) -> dict[str, object]:
    if int(config["training"]["epochs"]) not in {2, 40}:
        raise RuntimeError("Evaluator accepts only the 2-epoch smoke or frozen 40-epoch formal protocol.")
    set_seed(int(config["seed"]))
    device = select_device(config.get("device", "auto"))
    paths = ensure_output_dirs(str(Path(config["output_root"]) / variant))
    checkpoint = torch.load(paths["checkpoints"] / "best.pt", map_location=device, weights_only=False)
    classes = list(checkpoint["class_names"])
    model = build_qam_aware_model(variant, len(classes), **config["qam_aware"]).to(device).eval()
    model.load_state_dict(checkpoint["model_state"])

    dataset = SyntheticModulationDataset(
        int(config["dataset"]["test_samples"]), config["signal"], config["channel"], int(config["seed"]),
        "test", snr_values=config["dataset"]["snr_values"]
    )
    loader = DataLoader(dataset, batch_size=int(config["evaluation"]["batch_size"]), shuffle=False, num_workers=0)
    start = time.perf_counter()
    targets, predictions, confidence, logits = _predict_records(model, loader, device)
    elapsed = time.perf_counter() - start
    snr_values = list(config["dataset"]["snr_values"])
    assigned_snr = np.asarray([
        snr_values[(index % (len(classes) * len(snr_values))) // len(classes)] for index in range(len(dataset))
    ], dtype=np.float32)
    records = pd.DataFrame({
        "sample_index": np.arange(len(dataset)),
        "true_label": targets,
        "predicted_label": predictions,
        "true_modulation": [classes[index] for index in targets],
        "predicted_modulation": [classes[index] for index in predictions],
        "confidence": confidence,
        "snr_db": assigned_snr,
    })
    for index, name in enumerate(classes):
        records[f"logit_{name}"] = logits[:, index]
    records.to_csv(paths["tables"] / "development_test_predictions.csv", index=False)

    metrics = classification_metrics(targets, predictions, len(classes))
    matrix = np.asarray(metrics.pop("confusion_matrix"))
    save_confusion_matrix(
        matrix, classes, paths["figures"] / "development_confusion_matrix.png",
        paths["tables"] / "development_confusion_matrix.csv"
    )
    per_class = _per_class_metrics(targets, predictions, classes)
    per_class.to_csv(paths["tables"] / "development_per_class.csv", index=False)

    sweep_rows: list[dict[str, float | int]] = []
    sweep_class_rows: list[dict[str, float | int | str]] = []
    qam_rows: list[dict[str, float | int]] = []
    samples_per_class = int(config["evaluation"]["samples_per_modulation_per_snr"])
    for snr in config["evaluation"]["snr_values"]:
        sweep = SyntheticModulationDataset(
            samples_per_class * len(classes), config["signal"], config["channel"], int(config["seed"]),
            f"snr_sweep_{snr}", fixed_snr_db=float(snr)
        )
        sweep_loader = DataLoader(
            sweep, batch_size=int(config["evaluation"]["batch_size"]), shuffle=False, num_workers=0
        )
        sweep_targets, sweep_predictions, _, _ = _predict_records(model, sweep_loader, device)
        sweep_metrics = classification_metrics(sweep_targets, sweep_predictions, len(classes))
        sweep_matrix = np.asarray(sweep_metrics.pop("confusion_matrix"))
        per_snr_class = _per_class_metrics(sweep_targets, sweep_predictions, classes)
        sweep_rows.append({
            "snr_db": float(snr), "accuracy": sweep_metrics["accuracy"],
            "macro_f1": sweep_metrics["macro_f1"], "samples": len(sweep)
        })
        for row in per_snr_class.to_dict(orient="records"):
            sweep_class_rows.append({"snr_db": float(snr), **row})
        qam_rows.append({"snr_db": float(snr), **_qam_from_matrix(sweep_matrix, classes)})
        if float(snr) in {0.0, 10.0, 20.0}:
            pd.DataFrame(sweep_matrix, index=classes, columns=classes).to_csv(
                paths["tables"] / f"confusion_matrix_snr_{int(snr):+d}.csv"
            )

    sweep_frame = pd.DataFrame(sweep_rows)
    sweep_class_frame = pd.DataFrame(sweep_class_rows)
    qam_frame = pd.DataFrame(qam_rows)
    sweep_frame.to_csv(paths["tables"] / "snr_metrics.csv", index=False)
    sweep_class_frame.to_csv(paths["tables"] / "snr_per_modulation_metrics.csv", index=False)
    qam_frame.to_csv(paths["tables"] / "qam_snr_diagnostics.csv", index=False)
    high = qam_frame[qam_frame["snr_db"].isin([0.0, 10.0, 20.0])]
    qam_high_snr_mean = float(high[["16qam_accuracy", "64qam_accuracy"]].to_numpy().mean())

    for metric, filename in (("accuracy", "snr_accuracy.png"), ("macro_f1", "snr_f1.png")):
        figure, axis = plt.subplots(figsize=(8, 5))
        axis.plot(sweep_frame["snr_db"], sweep_frame[metric], marker="o", label=variant)
        axis.set(xlabel="SNR (dB)", ylabel=metric, ylim=(0, 1.02), title=f"{variant}: {metric} versus SNR")
        axis.grid(True, alpha=0.3)
        axis.legend()
        figure.tight_layout()
        figure.savefig(paths["figures"] / filename, dpi=180)
        plt.close(figure)
    figure, axis = plt.subplots(figsize=(8, 5))
    axis.plot(qam_frame["snr_db"], qam_frame["16qam_accuracy"], marker="o", label="16QAM")
    axis.plot(qam_frame["snr_db"], qam_frame["64qam_accuracy"], marker="o", label="64QAM")
    axis.set(xlabel="SNR (dB)", ylabel="Accuracy", ylim=(0, 1.02), title=f"{variant}: QAM accuracy versus SNR")
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(paths["figures"] / "qam_accuracy.png", dpi=180)
    plt.close(figure)

    cpu_model = model.to(torch.device("cpu"))
    summary = {
        "scope": "development_test and frozen snr_sweep only; final_blind_test was not accessed",
        "variant": variant,
        "best_epoch": int(checkpoint["epoch"]),
        "overall_accuracy": float(metrics["accuracy"]),
        "macro_f1": float(metrics["macro_f1"]),
        "per_class_accuracy": dict(zip(classes, per_class["accuracy"].tolist())),
        "per_class_f1": dict(zip(classes, per_class["f1"].tolist())),
        "development_qam": _qam_from_matrix(matrix, classes),
        "qam_high_snr_mean": qam_high_snr_mean,
        "single_sample_cpu_ms": benchmark_single_sample(cpu_model, int(config["signal"]["sample_length"]), torch.device("cpu")),
        "batch_throughput_records_per_sec": benchmark_throughput(
            cpu_model, int(config["signal"]["sample_length"]), int(config["evaluation"]["batch_size"]), torch.device("cpu")
        ),
        "end_to_end_development_records_per_sec": len(dataset) / elapsed,
        "environment": environment_info(),
        "git_commit": git_commit(),
    }
    (paths["tables"] / "evaluation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def evaluate_all(config_path: str) -> dict[str, object]:
    config = load_qam_aware_config(config_path)
    results = {variant: evaluate_variant(config, variant) for variant in config["variants"]}
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v2.yaml")
    args = parser.parse_args()
    print(json.dumps(evaluate_all(args.config), indent=2))


if __name__ == "__main__":
    main()
