"""SNR-accuracy and SNR-Macro-F1 sweep."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import torch
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from evaluation.confusion_matrix import save_confusion_matrix
from evaluation.evaluate import load_model, predict
from training.metrics import classification_metrics
from training.utils import ensure_output_dirs, load_config, select_device, set_seed


def run_snr_sweep(config: dict[str, Any], checkpoint_path: Path | None = None) -> pd.DataFrame:
    set_seed(int(config["seed"]))
    paths = ensure_output_dirs(config["output_dir"])
    device = select_device(config.get("device", "auto"))
    model, classes = load_model(config, checkpoint_path or paths["checkpoints"] / "best.pt", device)
    rows: list[dict[str, float]] = []
    per_class_rows: list[dict[str, float | str]] = []
    samples_per_class = int(config["evaluation"]["samples_per_modulation_per_snr"])
    total_per_snr = samples_per_class * len(classes)
    for snr in config["evaluation"]["snr_values"]:
        dataset = SyntheticModulationDataset(
            total_per_snr,
            config["signal"],
            config["channel"],
            seed=int(config["seed"]),
            split=f"snr_sweep_{snr}",
            fixed_snr_db=float(snr),
        )
        loader = DataLoader(dataset, batch_size=int(config["evaluation"]["batch_size"]), shuffle=False, num_workers=0)
        targets, predictions = predict(model, loader, device)
        metrics = classification_metrics(targets, predictions, len(classes))
        for class_name, accuracy in zip(classes, metrics["per_class_accuracy"]):
            per_class_rows.append({"snr_db": float(snr), "modulation": class_name, "accuracy": float(accuracy)})
        rows.append({
            "snr_db": float(snr),
            "samples": total_per_snr,
            "samples_per_modulation": samples_per_class,
            "accuracy": float(metrics["accuracy"]),
            "macro_f1": float(metrics["macro_f1"]),
        })
        print(f"SNR={snr:>5} dB accuracy={metrics['accuracy']:.4f} macro_f1={metrics['macro_f1']:.4f}")
        if float(snr) in {-10.0, -6.0, 0.0, 10.0, 20.0}:
            suffix = f"m{abs(int(snr))}" if float(snr) < 0 else f"p{int(snr)}"
            save_confusion_matrix(
                metrics["confusion_matrix"],
                classes,
                paths["figures"] / f"confusion_matrix_snr_{suffix}.png",
                paths["tables"] / f"confusion_matrix_snr_{suffix}.csv",
            )
    frame = pd.DataFrame(rows)
    frame.to_csv(paths["tables"] / "snr_metrics.csv", index=False)
    per_class_frame = pd.DataFrame(per_class_rows)
    per_class_frame.to_csv(paths["tables"] / "snr_per_modulation_accuracy.csv", index=False)
    for metric, label, filename in (
        ("accuracy", "Accuracy", "snr_accuracy.png"),
        ("macro_f1", "Macro-F1", "snr_f1.png"),
    ):
        fig, axis = plt.subplots(figsize=(8, 5))
        axis.plot(frame["snr_db"], frame[metric], marker="o", linewidth=1.8, label=f"Baseline CNN {label}")
        axis.set(title=f"{label} versus SNR", xlabel="SNR (dB)", ylabel=label)
        axis.set_ylim(0.0, 1.02)
        axis.grid(True, alpha=0.3)
        axis.legend()
        fig.tight_layout()
        fig.savefig(paths["figures"] / filename, dpi=180)
        plt.close(fig)
    fig, axis = plt.subplots(figsize=(10, 6))
    for class_name in classes:
        subset = per_class_frame[per_class_frame["modulation"] == class_name]
        axis.plot(subset["snr_db"], subset["accuracy"], marker="o", linewidth=1.5, label=class_name)
    axis.set(title="Per-modulation accuracy versus SNR", xlabel="SNR (dB)", ylabel="Accuracy", ylim=(0.0, 1.02))
    axis.grid(True, alpha=0.3)
    axis.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(paths["figures"] / "snr_accuracy_per_modulation.png", dpi=180)
    plt.close(fig)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/baseline.yaml")
    parser.add_argument("--checkpoint", default=None)
    args = parser.parse_args()
    run_snr_sweep(load_config(args.config), Path(args.checkpoint) if args.checkpoint else None)


if __name__ == "__main__":
    main()
