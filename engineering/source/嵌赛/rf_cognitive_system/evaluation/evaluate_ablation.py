"""Evaluate a Time/Frequency/Dual checkpoint on the frozen test and SNR rules."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import torch
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from evaluation.confusion_matrix import save_confusion_matrix
from evaluation.evaluate import benchmark_single_sample, benchmark_throughput, predict
from models.dual_domain_rfnet import build_ablation_model
from training.ablation_utils import load_ablation_config
from training.metrics import classification_metrics
from training.utils import ensure_output_dirs, select_device, set_seed


def _load(config: dict, variant: str, device: torch.device) -> tuple[torch.nn.Module, list[str], dict]:
    output_dir = str(Path(config["output_root"]) / variant)
    checkpoint = torch.load(ensure_output_dirs(output_dir)["checkpoints"] / "best.pt", map_location=device, weights_only=False)
    classes = list(checkpoint["class_names"])
    model = build_ablation_model(variant, len(classes), **config["dual_domain"])
    model.load_state_dict(checkpoint["model_state"])
    return model.to(device).eval(), classes, checkpoint


def evaluate_variant(config_path: str, variant: str) -> dict[str, object]:
    config = load_ablation_config(config_path)
    set_seed(int(config["seed"]))
    device = select_device(config.get("device", "auto"))
    paths = ensure_output_dirs(str(Path(config["output_root"]) / variant))
    model, classes, checkpoint = _load(config, variant, device)
    dataset = SyntheticModulationDataset(
        config["dataset"]["test_samples"], config["signal"], config["channel"], int(config["seed"]), "test", snr_values=config["dataset"].get("snr_values")
    )
    loader = DataLoader(dataset, batch_size=int(config["evaluation"]["batch_size"]), shuffle=False, num_workers=0)
    start = time.perf_counter()
    targets, predictions = predict(model, loader, device)
    elapsed = time.perf_counter() - start
    metrics = classification_metrics(targets, predictions, len(classes))
    matrix = metrics.pop("confusion_matrix")
    save_confusion_matrix(matrix, classes, paths["figures"] / "confusion_matrix.png", paths["tables"] / "confusion_matrix.csv")
    per_class = dict(zip(classes, metrics["per_class_accuracy"]))
    pd.DataFrame({"index": range(len(targets)), "target": targets, "prediction": predictions}).to_csv(
        paths["tables"] / "test_predictions.csv", index=False
    )

    sweep_rows = []
    per_class_rows = []
    samples_per_class = int(config["evaluation"]["samples_per_modulation_per_snr"])
    for snr in config["evaluation"]["snr_values"]:
        sweep = SyntheticModulationDataset(
            samples_per_class * len(classes), config["signal"], config["channel"], int(config["seed"]), f"snr_sweep_{snr}", fixed_snr_db=float(snr)
        )
        sweep_loader = DataLoader(sweep, batch_size=int(config["evaluation"]["batch_size"]), shuffle=False, num_workers=0)
        sweep_targets, sweep_predictions = predict(model, sweep_loader, device)
        result = classification_metrics(sweep_targets, sweep_predictions, len(classes))
        sweep_rows.append({"snr_db": snr, "accuracy": result["accuracy"], "macro_f1": result["macro_f1"], "samples": len(sweep)})
        per_class_rows.extend(
            {"snr_db": snr, "modulation": name, "accuracy": accuracy}
            for name, accuracy in zip(classes, result["per_class_accuracy"])
        )
    sweep_frame = pd.DataFrame(sweep_rows)
    sweep_frame.to_csv(paths["tables"] / "snr_metrics.csv", index=False)
    pd.DataFrame(per_class_rows).to_csv(paths["tables"] / "snr_per_modulation_accuracy.csv", index=False)
    for metric, name in (("accuracy", "snr_accuracy.png"), ("macro_f1", "snr_f1.png")):
        fig, axis = plt.subplots(figsize=(8, 5))
        axis.plot(sweep_frame["snr_db"], sweep_frame[metric], marker="o", label=variant)
        axis.set(title=f"{variant}: {metric} versus SNR", xlabel="SNR (dB)", ylabel=metric, ylim=(0, 1.02))
        axis.grid(True, alpha=0.3)
        axis.legend()
        fig.tight_layout()
        fig.savefig(paths["figures"] / name, dpi=170)
        plt.close(fig)
    summary = {
        "variant": variant,
        "best_epoch": int(checkpoint["epoch"]),
        "overall_accuracy": metrics["accuracy"],
        "macro_f1": metrics["macro_f1"],
        "per_class_accuracy": per_class,
        "single_sample_cpu_ms": benchmark_single_sample(model, int(config["signal"]["sample_length"]), device),
        "batch_throughput_records_per_sec": benchmark_throughput(model, int(config["signal"]["sample_length"]), int(config["evaluation"]["batch_size"]), device),
        "end_to_end_records_per_sec": len(dataset) / elapsed,
    }
    (paths["tables"] / "test_metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/dual_domain_v1.yaml")
    parser.add_argument("--variant", required=True, choices=("time_only", "frequency_only", "time_only_wide", "dual"))
    args = parser.parse_args()
    print(json.dumps(evaluate_variant(args.config, args.variant), indent=2))


if __name__ == "__main__":
    main()
