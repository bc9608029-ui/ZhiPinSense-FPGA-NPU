"""V2 evaluation.

Phase A/B reuse V1's ``evaluate_v1_1`` and ``ood_channels`` verbatim (the V2
baseline is the same ADAMRV11Net + synthetic generator, so V1's leakage-safe
validation applies unchanged).  Phase C candidates use the generic
``evaluate_candidate`` below, which mirrors ``evaluate_v1_1`` with a pluggable
model builder and still enforces the same selection-split guard.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

import torch
from torch.utils.data import DataLoader

from datasets.ad_amr_v1_1_dataset import ADAMRV11Dataset, assert_selection_split, collate_ad_amr
from evaluation.evaluate_ad_amr_v1_1 import evaluate_v1_1, ood_channels
from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model
from training.ad_amr_v1_1_trainer import _summary
from training.utils import load_yaml, select_device

DEFAULT_SPLIT = "ad_amr_v1_1_validation"

__all__ = ["evaluate_v1_1", "ood_channels", "evaluate_ood", "evaluate_candidate",
           "apply_fake_int8", "DEFAULT_SPLIT"]


def apply_fake_int8(model: torch.nn.Module) -> None:
    """In-place fake symmetric INT8 weight quantization (mirrors V1 evaluate)."""
    with torch.no_grad():
        for parameter in model.parameters():
            maximum = float(parameter.abs().max())
            if maximum > 0.0:
                scale = maximum / 127.0
                parameter.copy_(torch.clamp(torch.round(parameter / scale), -127, 127) * scale)


def evaluate_ood(config: dict[str, Any] | str, checkpoint_path: str | Path,
                 samples: int | None = None, fake_int8: bool = False,
                 domains: list[str] | None = None,
                 build_fn: Callable[..., torch.nn.Module] | None = None) -> dict[str, Any]:
    """Evaluate the checkpoint under each OOD channel domain."""
    config_dict = copy.deepcopy(config) if isinstance(config, dict) else load_yaml(config)
    domains_cfg = ood_channels(config_dict["channel"])
    selected = domains or list(domains_cfg)
    results: dict[str, Any] = {}
    for name in selected:
        if name not in domains_cfg:
            raise ValueError(f"unknown OOD domain {name!r}")
        if build_fn is None:
            results[name] = evaluate_v1_1(
                config_dict, checkpoint_path, split=DEFAULT_SPLIT,
                channel=domains_cfg[name], samples=samples, fake_int8=fake_int8,
            )
        else:
            results[name] = evaluate_candidate(
                config_dict, checkpoint_path, build_fn, split=DEFAULT_SPLIT,
                channel=domains_cfg[name], samples=samples, fake_int8=fake_int8,
            )
    return results


def evaluate_candidate(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path,
                       build_fn: Callable[..., torch.nn.Module],
                       split: str = DEFAULT_SPLIT, channel: dict[str, Any] | None = None,
                       samples: int | None = None, fake_int8: bool = False) -> dict[str, Any]:
    """Generic V1.1-compatible evaluator for a Phase-C candidate builder."""
    assert_selection_split(split)
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    device = select_device(config.get("device", "auto"))
    classes = [str(v).upper() for v in config["signal"]["modulations"]]
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if list(checkpoint.get("class_names", [])) != classes:
        raise RuntimeError("checkpoint and evaluation class orders differ")
    model = build_fn(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    if fake_int8:
        apply_fake_int8(model)
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
    return {
        "checkpoint": str(checkpoint_path), "checkpoint_epoch": int(checkpoint["epoch"]),
        "split": split, "seed": int(config["seed"]), "samples": count,
        "classes": classes, "metrics": metrics,
        "numeric_mode": "fake_symmetric_int8_weights_fp32_activations" if fake_int8 else "fp32",
        "final_blind_test_accessed": False,
    }
