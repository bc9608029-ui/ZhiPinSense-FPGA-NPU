"""Development evaluation for QAM-Aware V3.2 without touching the blind set.

Evaluates a single ``v2_compatible`` suite on the exact frozen-V2 development
test namespace (same seed, split and channel as the V2 champion).  The
``v3_2_final_blind_test`` namespace is never instantiated.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import confusion_matrix, f1_score
from torch.utils.data import DataLoader

from datasets.synthetic_dataset import SyntheticModulationDataset
from models.qam_aware_rfnet_v3_2 import build_qam_aware_v3_2
from training.metrics import classification_metrics
from training.qam_aware_v3_2_utils import load_qam_aware_v3_2_config
from training.utils import ensure_output_dirs, load_config, select_device, set_seed


@torch.inference_mode()
def _predict(model: torch.nn.Module, loader: DataLoader, device: torch.device) -> tuple[np.ndarray, np.ndarray]:
    targets: list[int] = []
    predictions: list[int] = []
    model.eval()
    for inputs, labels in loader:
        logits = model(inputs.to(device, non_blocking=True))
        if not torch.isfinite(logits).all():
            raise RuntimeError("V3.2 evaluation produced NaN/Inf logits")
        targets.extend(labels.tolist())
        predictions.extend(logits.argmax(dim=1).cpu().tolist())
    return np.asarray(targets, dtype=np.int64), np.asarray(predictions, dtype=np.int64)


def _per_class(targets: np.ndarray, predictions: np.ndarray, classes: list[str]) -> pd.DataFrame:
    matrix = confusion_matrix(targets, predictions, labels=np.arange(len(classes)))
    count = matrix.sum(axis=1)
    accuracy = np.divide(np.diag(matrix), count, out=np.zeros(len(classes), dtype=float), where=count > 0)
    f1 = f1_score(targets, predictions, labels=np.arange(len(classes)), average=None, zero_division=0)
    return pd.DataFrame({"modulation": classes, "accuracy": accuracy, "f1": f1, "samples": count})


def _evaluate_suite(
    *,
    model: torch.nn.Module,
    device: torch.device,
    config: dict,
    suite_config: dict,
    channel_config: dict,
    classes: list[str],
    seed: int,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, np.ndarray]:
    batch_size = int(config["evaluation"]["batch_size"])
    dataset = SyntheticModulationDataset(
        int(suite_config["dataset"]["test_samples"]),
        config["signal"],
        channel_config,
        seed,
        "test",
        snr_values=suite_config["dataset"]["snr_values"],
    )
    targets, predictions = _predict(
        model, DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0), device
    )
    metrics = classification_metrics(targets, predictions, len(classes))
    matrix = np.asarray(metrics.pop("confusion_matrix"))
    per_class = _per_class(targets, predictions, classes)

    snr_rows: list[dict[str, float | int]] = []
    count = int(suite_config["evaluation"]["samples_per_modulation_per_snr"])
    for snr in suite_config["evaluation"]["snr_values"]:
        sweep = SyntheticModulationDataset(
            count * len(classes),
            config["signal"],
            channel_config,
            seed,
            f"snr_sweep_{snr}",
            fixed_snr_db=float(snr),
        )
        sweep_targets, sweep_predictions = _predict(
            model, DataLoader(sweep, batch_size=batch_size, shuffle=False, num_workers=0), device
        )
        result = classification_metrics(sweep_targets, sweep_predictions, len(classes))
        snr_rows.append(
            {
                "snr_db": float(snr),
                "accuracy": float(result["accuracy"]),
                "macro_f1": float(result["macro_f1"]),
                "samples": len(sweep),
            }
        )
    qam = per_class[per_class["modulation"].isin(["16QAM", "64QAM"])]
    summary: dict[str, object] = {
        "suite": "v2_compatible",
        "scope": "development-only; v3_2_final_blind_test was not accessed",
        "exact_v2_test_namespace": True,
        "samples": len(dataset),
        "accuracy": float(metrics["accuracy"]),
        "macro_f1": float(metrics["macro_f1"]),
        "qam_mean_accuracy": float(qam["accuracy"].mean()),
        "per_class_accuracy": dict(zip(per_class["modulation"], per_class["accuracy"])),
        "per_class_f1": dict(zip(per_class["modulation"], per_class["f1"])),
    }
    return summary, per_class, pd.DataFrame(snr_rows), matrix


def evaluate_v3_2(config_path: str, checkpoint_path: str | None = None) -> dict[str, object]:
    config = load_qam_aware_v3_2_config(config_path)
    set_seed(int(config["seed"]))
    device = select_device(str(config.get("device", "auto")))
    paths = ensure_output_dirs(config["output_root"])
    checkpoint_file = Path(checkpoint_path) if checkpoint_path else paths["checkpoints"] / "best.pt"
    checkpoint = torch.load(checkpoint_file, map_location=device, weights_only=False)
    classes = [str(name).upper() for name in config["signal"]["modulations"]]
    model = build_qam_aware_v3_2(len(classes), **config["model"]).to(device).eval()
    model.load_state_dict(checkpoint["model_state"])

    baseline = load_config(config["_baseline_path"])
    suite_config = config if int(config["training"]["epochs"]) <= 2 else baseline

    summary, per_class, by_snr, matrix = _evaluate_suite(
        model=model,
        device=device,
        config=config,
        suite_config=suite_config,
        channel_config=baseline["channel"],
        classes=classes,
        seed=int(config["seed"]),
    )
    report: dict[str, object] = {
        "checkpoint": str(checkpoint_file),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "final_blind_test_accessed": False,
        "suites": {"v2_compatible": summary},
    }
    per_class.to_csv(paths["tables"] / "v2_compatible_per_class.csv", index=False)
    by_snr.to_csv(paths["tables"] / "v2_compatible_snr_metrics.csv", index=False)
    pd.DataFrame(matrix, index=classes, columns=classes).to_csv(
        paths["tables"] / "v2_compatible_confusion_matrix.csv"
    )
    (paths["tables"] / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_2_smoke.yaml")
    parser.add_argument("--checkpoint", default=None)
    args = parser.parse_args()
    print(json.dumps(evaluate_v3_2(args.config, args.checkpoint), indent=2))


if __name__ == "__main__":
    main()
