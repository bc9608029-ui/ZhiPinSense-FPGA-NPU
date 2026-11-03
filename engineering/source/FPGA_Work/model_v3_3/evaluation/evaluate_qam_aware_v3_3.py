"""Development evaluation for QAM-Aware V3.3 without touching the blind set.

Two evaluation surfaces are provided:

* ``evaluate_v3_3`` — the formal development-test suite (``"test"`` namespace,
  the exact V2 development test: seed 2026, 21 SNR).  This is only invoked by
  the *formal* three-seed stage, never by Stage-1 candidate selection.
* ``evaluate_v3_3_validation`` / ``evaluate_v3_3_a0_validation`` — the
  validation-only surface used by Stage-1 candidate selection.  They rank on the
  ``v3_3_validation`` namespace with the *selection seed* (so two selection seeds
  change both training randomness and the validation data seed), never on
  ``"test"``.

Every dataset split is recorded via :mod:`training.v3_3_split_guard`, so Stage-1
can save an access audit proving ``"test"`` and ``v3_3_final_blind_test`` were
never instantiated.
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
from models.qam_aware_rfnet_v3_3 import build_qam_aware_v3_3, load_v2_into_v3_3
from training.metrics import classification_metrics
from training.qam_aware_v3_3_utils import load_qam_aware_v3_3_config
from training.utils import ensure_output_dirs, load_config, select_device, set_seed
from training.v3_3_split_guard import record_split


@torch.inference_mode()
def _predict(model: torch.nn.Module, loader: DataLoader, device: torch.device) -> tuple[np.ndarray, np.ndarray]:
    targets: list[int] = []
    predictions: list[int] = []
    model.eval()
    for inputs, labels in loader:
        logits = model(inputs.to(device, non_blocking=True))
        if not torch.isfinite(logits).all():
            raise RuntimeError("V3.3 evaluation produced NaN/Inf logits")
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
    channel_config: dict,
    classes: list[str],
    seed: int,
    split: str,
    samples: int,
    snr_values: list[float],
    sweep_split: str | None = None,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, np.ndarray]:
    record_split(split)
    batch_size = int(config["evaluation"]["batch_size"])
    dataset = SyntheticModulationDataset(
        int(samples),
        config["signal"],
        channel_config,
        seed,
        split,
        snr_values=snr_values,
    )
    targets, predictions = _predict(
        model, DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0), device
    )
    metrics = classification_metrics(targets, predictions, len(classes))
    matrix = np.asarray(metrics.pop("confusion_matrix"))
    per_class = _per_class(targets, predictions, classes)

    snr_rows: list[dict[str, float | int]] = []
    if sweep_split is not None:
        count = int(config["evaluation"]["samples_per_modulation_per_snr"])
        for snr in snr_values:
            record_split(f"{sweep_split}_{snr}")
            sweep = SyntheticModulationDataset(
                count * len(classes),
                config["signal"],
                channel_config,
                seed,
                f"{sweep_split}_{snr}",
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
        "suite": "v2_compatible" if split == "test" else "validation",
        "split": split,
        "scope": "development-only; v3_3_final_blind_test was not accessed",
        "exact_v2_test_namespace": split == "test",
        "seed": int(seed),
        "samples": len(dataset),
        "accuracy": float(metrics["accuracy"]),
        "macro_f1": float(metrics["macro_f1"]),
        "qam_mean_accuracy": float(qam["accuracy"].mean()),
        "per_class_accuracy": dict(zip(per_class["modulation"], per_class["accuracy"])),
        "per_class_f1": dict(zip(per_class["modulation"], per_class["f1"])),
    }
    return summary, per_class, pd.DataFrame(snr_rows), matrix


def _fpga_sim_gap(
    *,
    checkpoint: dict,
    config: dict,
    channel_config: dict,
    classes: list[str],
    device: torch.device,
    seed: int,
    split: str,
    samples: int,
    snr_values: list[float],
) -> dict[str, object]:
    """Compare full-precision vs FPGA Mandatory-Core emulated numeric domain.

    The gap is measured on the identical namespace (``split``/``seed``) so it
    reflects only the input numeric-domain (Q15 -> SInt8 -> host dequant), never
    a different dataset.  It is not a real-board measurement.
    """

    fp32_config = dict(config["model"])
    fp32_config["simulate_hardware_inputs"] = False
    hw_config = dict(config["model"])
    hw_config["simulate_hardware_inputs"] = True

    fp32_model = build_qam_aware_v3_3(len(classes), **fp32_config).to(device).eval()
    fp32_model.load_state_dict(checkpoint["model_state"])
    hw_model = build_qam_aware_v3_3(len(classes), **hw_config).to(device).eval()
    hw_model.load_state_dict(checkpoint["model_state"])

    fp32_summary, _, _, _ = _evaluate_suite(
        model=fp32_model, device=device, config=config, channel_config=channel_config,
        classes=classes, seed=seed, split=split, samples=samples, snr_values=snr_values,
    )
    hw_summary, _, _, _ = _evaluate_suite(
        model=hw_model, device=device, config=config, channel_config=channel_config,
        classes=classes, seed=seed, split=split, samples=samples, snr_values=snr_values,
    )
    return {
        "scope": "FP32 vs FPGA Mandatory-Core emulation; not a real-board measurement",
        "split": split,
        "seed": int(seed),
        "fp32_accuracy": float(fp32_summary["accuracy"]),
        "fp32_macro_f1": float(fp32_summary["macro_f1"]),
        "fpga_sim_accuracy": float(hw_summary["accuracy"]),
        "fpga_sim_macro_f1": float(hw_summary["macro_f1"]),
        "accuracy_gap": float(fp32_summary["accuracy"]) - float(hw_summary["accuracy"]),
        "macro_f1_gap": float(fp32_summary["macro_f1"]) - float(hw_summary["macro_f1"]),
    }


def evaluate_v3_3(config_path: str, checkpoint_path: str | None = None) -> dict[str, object]:
    config = load_qam_aware_v3_3_config(config_path)
    baseline = load_config(config["_baseline_path"])
    eval_seed = int(baseline["seed"])
    set_seed(eval_seed)
    device = select_device(str(config.get("device", "auto")))
    paths = ensure_output_dirs(config["output_root"])
    checkpoint_file = Path(checkpoint_path) if checkpoint_path else paths["checkpoints"] / "best.pt"
    checkpoint = torch.load(checkpoint_file, map_location=device, weights_only=False)
    classes = [str(name).upper() for name in config["signal"]["modulations"]]
    model = build_qam_aware_v3_3(len(classes), **config["model"]).to(device).eval()
    model.load_state_dict(checkpoint["model_state"])

    suite_config = config if int(config["training"]["epochs"]) <= 2 else baseline
    samples = int(suite_config["dataset"]["test_samples"])
    snr_values = [float(value) for value in suite_config["evaluation"]["snr_values"]]

    summary, per_class, by_snr, matrix = _evaluate_suite(
        model=model, device=device, config=config, channel_config=baseline["channel"],
        classes=classes, seed=eval_seed, split="test", samples=samples,
        snr_values=snr_values, sweep_split="snr_sweep",
    )

    fpga_sim_gap = _fpga_sim_gap(
        checkpoint=checkpoint, config=config, channel_config=baseline["channel"],
        classes=classes, device=device, seed=eval_seed, split="test", samples=samples,
        snr_values=snr_values,
    )

    report: dict[str, object] = {
        "checkpoint": str(checkpoint_file),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "final_blind_test_accessed": False,
        "suites": {"v2_compatible": summary},
        "fpga_sim_gap": fpga_sim_gap,
    }
    per_class.to_csv(paths["tables"] / "v2_compatible_per_class.csv", index=False)
    by_snr.to_csv(paths["tables"] / "v2_compatible_snr_metrics.csv", index=False)
    pd.DataFrame(matrix, index=classes, columns=classes).to_csv(
        paths["tables"] / "v2_compatible_confusion_matrix.csv"
    )
    (paths["tables"] / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _validation_suite_settings(config: dict) -> tuple[int, list[float]]:
    samples = int(config["dataset"]["val_samples"])
    snr_values = [float(value) for value in config["evaluation"]["snr_values"]]
    return samples, snr_values


def evaluate_v3_3_validation(
    config_path: str,
    checkpoint_path: str | None = None,
    *,
    seed: int,
    samples: int | None = None,
) -> dict[str, object]:
    """Evaluate a trained V3.3 checkpoint on the validation namespace.

    Uses the ``v3_3_validation`` split with ``seed`` as the data seed — the exact
    held-out surface Stage-1 candidate selection ranks on.  Never touches
    ``"test"`` or the final blind namespace.
    """

    config = load_qam_aware_v3_3_config(config_path)
    baseline = load_config(config["_baseline_path"])
    set_seed(seed)
    device = select_device(str(config.get("device", "auto")))
    paths = ensure_output_dirs(config["output_root"])
    checkpoint_file = Path(checkpoint_path) if checkpoint_path else paths["checkpoints"] / "best.pt"
    checkpoint = torch.load(checkpoint_file, map_location=device, weights_only=False)
    classes = [str(name).upper() for name in config["signal"]["modulations"]]
    model = build_qam_aware_v3_3(len(classes), **config["model"]).to(device).eval()
    model.load_state_dict(checkpoint["model_state"])

    default_samples, snr_values = _validation_suite_settings(config)
    samples = default_samples if samples is None else int(samples)

    summary, _, _, _ = _evaluate_suite(
        model=model, device=device, config=config, channel_config=baseline["channel"],
        classes=classes, seed=seed, split="v3_3_validation", samples=samples,
        snr_values=snr_values,
    )
    fpga_sim_gap = _fpga_sim_gap(
        checkpoint=checkpoint, config=config, channel_config=baseline["channel"],
        classes=classes, device=device, seed=seed, split="v3_3_validation",
        samples=samples, snr_values=snr_values,
    )
    return {
        "checkpoint": str(checkpoint_file),
        "checkpoint_epoch": int(checkpoint["epoch"]),
        "final_blind_test_accessed": False,
        "validation_seed": int(seed),
        "validation": summary,
        "fpga_sim_gap": fpga_sim_gap,
    }


def evaluate_v3_3_a0_validation(
    config_path: str,
    v2_checkpoint_path: str | None = None,
    *,
    seed: int,
    samples: int | None = None,
) -> dict[str, object]:
    """Evaluate the *real* frozen V2 champion (A0) on the validation namespace.

    A0 is not a copied metric from the acceptance YAML: the frozen V2 checkpoint
    is loaded strictly into a V3.3 wrapper with the residual expert disabled, then
    re-inferred on the same validation seed (FP32 + FPGA-sim) as the A1-A3
    candidates.  This lets A0 genuinely win or lose selection on identical ground.
    """

    config = load_qam_aware_v3_3_config(config_path)
    baseline = load_config(config["_baseline_path"])
    v2_path = Path(v2_checkpoint_path) if v2_checkpoint_path else Path(config["v2_checkpoint"])
    set_seed(seed)
    device = select_device(str(config.get("device", "auto")))
    classes = [str(name).upper() for name in config["signal"]["modulations"]]

    v2_checkpoint = torch.load(v2_path, map_location=device, weights_only=False)
    a0_model_config = dict(config["model"])
    a0_model_config["residual_expert"] = {"enabled": False}
    a0_model_config["family_aux"] = {"enabled": False}
    model = build_qam_aware_v3_3(len(classes), **a0_model_config).to(device).eval()
    load_v2_into_v3_3(model, v2_checkpoint)

    default_samples, snr_values = _validation_suite_settings(config)
    samples = default_samples if samples is None else int(samples)

    summary, _, _, _ = _evaluate_suite(
        model=model, device=device, config=config, channel_config=baseline["channel"],
        classes=classes, seed=seed, split="v3_3_validation", samples=samples,
        snr_values=snr_values,
    )
    # The A0 wrapper has no expert, so a V3.3 checkpoint does not exist; rebuild
    # the full-precision / hardware-sim pair directly from the V2 backbone state.
    fpga_sim_gap = _a0_fpga_sim_gap(
        model=model, v2_checkpoint=v2_checkpoint, config=config,
        channel_config=baseline["channel"], classes=classes, device=device,
        seed=seed, samples=samples, snr_values=snr_values,
    )
    return {
        "checkpoint": str(v2_path),
        "final_blind_test_accessed": False,
        "validation_seed": int(seed),
        "validation": summary,
        "fpga_sim_gap": fpga_sim_gap,
    }


def _a0_fpga_sim_gap(
    *,
    model: torch.nn.Module,
    v2_checkpoint: dict,
    config: dict,
    channel_config: dict,
    classes: list[str],
    device: torch.device,
    seed: int,
    samples: int,
    snr_values: list[float],
) -> dict[str, object]:
    """FPGA-sim gap for A0 (frozen V2), which has no V3.3 checkpoint to reload."""

    fp32_model = model
    hw_config = dict(config["model"])
    hw_config["simulate_hardware_inputs"] = True
    hw_config["residual_expert"] = {"enabled": False}
    hw_config["family_aux"] = {"enabled": False}
    hw_model = build_qam_aware_v3_3(len(classes), **hw_config).to(device).eval()
    load_v2_into_v3_3(hw_model, v2_checkpoint)

    fp32_summary, _, _, _ = _evaluate_suite(
        model=fp32_model, device=device, config=config, channel_config=channel_config,
        classes=classes, seed=seed, split="v3_3_validation", samples=samples,
        snr_values=snr_values,
    )
    hw_summary, _, _, _ = _evaluate_suite(
        model=hw_model, device=device, config=config, channel_config=channel_config,
        classes=classes, seed=seed, split="v3_3_validation", samples=samples,
        snr_values=snr_values,
    )
    return {
        "scope": "FP32 vs FPGA Mandatory-Core emulation; not a real-board measurement",
        "split": "v3_3_validation",
        "seed": int(seed),
        "fp32_accuracy": float(fp32_summary["accuracy"]),
        "fp32_macro_f1": float(fp32_summary["macro_f1"]),
        "fpga_sim_accuracy": float(hw_summary["accuracy"]),
        "fpga_sim_macro_f1": float(hw_summary["macro_f1"]),
        "accuracy_gap": float(fp32_summary["accuracy"]) - float(hw_summary["accuracy"]),
        "macro_f1_gap": float(fp32_summary["macro_f1"]) - float(hw_summary["macro_f1"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_3_smoke.yaml")
    parser.add_argument("--checkpoint", default=None)
    args = parser.parse_args()
    print(json.dumps(evaluate_v3_3(args.config, args.checkpoint), indent=2))


if __name__ == "__main__":
    main()
