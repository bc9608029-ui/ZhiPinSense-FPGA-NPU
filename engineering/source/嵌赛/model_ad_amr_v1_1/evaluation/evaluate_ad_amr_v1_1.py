"""Leakage-safe validation and OOD evaluation for V1.1."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from datasets.ad_amr_v1_1_dataset import ADAMRV11Dataset, assert_selection_split, collate_ad_amr
from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model
from training.ad_amr_v1_1_trainer import _summary
from training.utils import load_yaml, save_json, select_device


def ood_channels(base: dict[str, Any]) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, dict[str, Any]]] = {
        "cfo_strong": {"cfo": {"hz": [-2500.0, 2500.0]}},
        "phase_noise": {"phase_noise": {"std_rad": [0.004, 0.012]}},
        "iq_imbalance": {"iq_imbalance": {"gain_db": [-2.0, 2.0], "phase_deg": [-10.0, 10.0]}},
        "multipath": {"multipath": {"num_taps": [3, 6], "max_delay": 20}},
        "clipping": {"clipping": {"level_rms": [0.8, 1.4]}},
        "multi_impairment": {
            "cfo": {"hz": [-1800.0, 1800.0]},
            "phase_noise": {"std_rad": [0.002, 0.008]},
            "iq_imbalance": {"gain_db": [-1.5, 1.5], "phase_deg": [-8.0, 8.0]},
            "multipath": {"num_taps": [2, 5], "max_delay": 16},
        },
    }
    effect_names = (
        "rayleigh", "rician", "multipath", "cfo", "phase_offset", "phase_noise", "sfo",
        "iq_imbalance", "dc_offset", "amplitude_scaling", "clipping",
        "narrowband_interference", "burst_interference",
    )
    result: dict[str, dict[str, Any]] = {}
    for domain, effects in specs.items():
        cfg = copy.deepcopy(base)
        cfg["domain_randomization"] = False
        for name in effect_names:
            cfg.setdefault(name, {})["enabled"] = False
            cfg[name]["probability"] = 0.0
        cfg.setdefault("awgn", {}).update({"enabled": True, "probability": 1.0})
        for name, overrides in effects.items():
            cfg.setdefault(name, {}).update(overrides)
            cfg[name].update({"enabled": True, "probability": 1.0})
        result[domain] = cfg
    return result


def _rated_per_class(targets: list[int], predictions: list[int], snrs: list[float],
                     num_classes: int) -> list[float]:
    values: list[float] = []
    for class_index in range(num_classes):
        selected = [p == t for p, t, s in zip(predictions, targets, snrs)
                    if t == class_index and 0.0 <= s <= 20.0]
        values.append(float(sum(selected) / len(selected)) if selected else 0.0)
    return values


def evaluate_v1_1(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path,
                  split: str = "ad_amr_v1_1_validation", channel: dict[str, Any] | None = None,
                  samples: int | None = None, fake_int8: bool = False) -> dict[str, Any]:
    assert_selection_split(split)
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    device = select_device(config.get("device", "auto"))
    classes = [str(v).upper() for v in config["signal"]["modulations"]]
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if list(checkpoint.get("class_names", [])) != classes:
        raise RuntimeError("checkpoint and evaluation class orders differ")
    model = build_ad_amr_v1_1_model(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    if fake_int8:
        with torch.no_grad():
            for parameter in model.parameters():
                maximum = float(parameter.abs().max())
                if maximum > 0.0:
                    scale = maximum / 127.0
                    parameter.copy_(torch.clamp(torch.round(parameter / scale), -127, 127) * scale)
    model = model.to(device).eval()
    count = int(samples or config["evaluation"]["samples"])
    dataset = ADAMRV11Dataset(
        count, config["signal"], channel or config["channel"], int(config["seed"]), split,
        snr_values=[float(v) for v in config["dataset"]["snr_values"]],
    )
    loader = DataLoader(dataset, batch_size=int(config["evaluation"]["batch_size"]),
                        shuffle=False, num_workers=0, collate_fn=collate_ad_amr,
                        pin_memory=device.type == "cuda")
    targets: list[int] = []
    predictions: list[int] = []
    snrs: list[float] = []
    with torch.inference_mode():
        for batch in loader:
            logits, _ = model(batch["noisy_iq"].to(device, non_blocking=True))
            if not bool(torch.isfinite(logits).all()):
                raise RuntimeError(f"non-finite logits in {split}")
            targets.extend(batch["label"].tolist())
            predictions.extend(logits.argmax(1).cpu().tolist())
            snrs.extend(float(v) for v in batch["snr_db"].tolist())
    metrics = _summary(targets, predictions, snrs, len(classes))
    rated = _rated_per_class(targets, predictions, snrs, len(classes))
    metrics["rated_per_class_accuracy"] = dict(zip(classes, rated))
    metrics["min_rated_class_accuracy"] = min(rated)
    result = {
        "checkpoint": str(checkpoint_path), "checkpoint_epoch": int(checkpoint["epoch"]),
        "split": split, "seed": int(config["seed"]), "samples": count,
        "classes": classes, "metrics": metrics,
        "numeric_mode": "fake_symmetric_int8_weights_fp32_activations" if fake_int8 else "fp32",
        "final_blind_test_accessed": False,
    }
    return result


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1_1.yaml")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--out", default="outputs/ad_amr_v1_1/evaluation.json")
    args = parser.parse_args()
    report = evaluate_v1_1(args.config, args.checkpoint)
    save_json(report, args.out)
    print(report["metrics"])


if __name__ == "__main__":
    main()
