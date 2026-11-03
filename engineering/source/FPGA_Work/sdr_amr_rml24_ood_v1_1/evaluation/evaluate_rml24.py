"""RadioML2018.01A 24-class closed-set evaluation + channel-covariate OOD.

Closed-set evaluation runs the audited RadioML split through the 24-class head
and reuses V1's ``_summary`` for the shared selection metric.  The channel-
covariate axis applies the frozen channel-impairment domains to *received* ID
samples (CFO / phase noise / IQ imbalance / multipath / clipping / multi) and
reports the closed-set accuracy under each shift — the "ID covariate shift must
still be recognized, not rejected" axis, distinct from semantic OOD.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset

from channel.channel_pipeline import ChannelPipeline
from contracts.rml24_contract import LABEL_ORDER_24
from datasets.ad_amr_dataset import collate_ad_amr
from datasets.radioml2018_dataset import RadioML2018Dataset
from evaluation.evaluate_ad_amr_v1_1 import ood_channels
from models.rml24_net import build_rml24_model
from training.ad_amr_v1_1_trainer import _summary
from training.utils import load_yaml, select_device

RADIOML_SAMPLE_RATE_HZ = 200_000.0


def _apply_fake_int8(model: torch.nn.Module) -> None:
    with torch.no_grad():
        for parameter in model.parameters():
            maximum = float(parameter.abs().max())
            if maximum > 0.0:
                scale = maximum / 127.0
                parameter.copy_(torch.clamp(torch.round(parameter / scale), -127, 127) * scale)


_QAM_PSK_INDICES = (3, 4, 5, 6, 7, 12, 13, 14, 15, 16)


def _confusion_matrix(targets: np.ndarray, predictions: np.ndarray, num_classes: int) -> np.ndarray:
    """Row=target, column=prediction integer confusion matrix."""
    targets = np.asarray(targets, dtype=np.int64)
    predictions = np.asarray(predictions, dtype=np.int64)
    if targets.shape != predictions.shape:
        raise ValueError("targets and predictions shapes differ")
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    np.add.at(cm, (targets, predictions), 1)
    return cm


def _per_class_recall(cm: np.ndarray) -> list[float]:
    """Per-class recall = diagonal / row-sum (== per-class accuracy in a
    multi-class confusion matrix)."""
    cm = np.asarray(cm, dtype=np.float64)
    row_sum = cm.sum(axis=1)
    return [float(cm[i, i] / row_sum[i]) if row_sum[i] > 0 else 0.0
            for i in range(cm.shape[0])]


def _near_qam_psk_confusion(cm: np.ndarray) -> dict[str, Any]:
    """Confusion restricted to the near QAM/PSK block (QAM 12-16, PSK 3-7)."""
    cm = np.asarray(cm, dtype=np.int64)
    idx = _QAM_PSK_INDICES
    return {"indices": list(idx),
            "class_names": [LABEL_ORDER_24[i] for i in idx],
            "matrix": cm[np.ix_(idx, idx)].tolist()}


def _load_model(config: dict[str, Any], checkpoint_path: str | Path,
                fake_int8: bool, device: torch.device) -> tuple[torch.nn.Module, dict[str, Any]]:
    classes = list(LABEL_ORDER_24)
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if list(checkpoint.get("class_names", [])) != classes:
        raise RuntimeError("24-class checkpoint class order differs from the frozen contract")
    model = build_rml24_model(len(classes), **config["model"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    if fake_int8:
        _apply_fake_int8(model)
    return model.to(device).eval(), checkpoint


def _stratified_indices(labels: np.ndarray, snrs: np.ndarray, limit: int,
                        seed: int) -> list[int]:
    """Deterministic representative subset across (class, SNR) strata.

    The split index arrays are concatenated in sorted ``(label, snr)`` order
    (``audit_radioml2018``), so taking a prefix would be label-major biased: the
    first ``int(4096 * 0.2) * k`` validation samples are the first ``k`` SNR
    strata of class 0 (OOK) only.  Allocate the budget proportionally to each
    stratum's size and draw a fixed per-stratum shuffle, so the subset keeps the
    same class/SNR distribution as the full split.  This keeps a bounded
    ``rated_0_20_accuracy`` representative of all 24 classes (the selection metric
    must match the epoch-log caliber, which is computed on the full validation
    split).
    """
    n = int(len(labels))
    if limit >= n:
        return list(range(n))
    strata: dict[tuple[int, float], list[int]] = {}
    for position in range(n):
        strata.setdefault((int(labels[position]), float(snrs[position])), []).append(position)
    allocations = {key: int(len(positions) * limit / n) for key, positions in strata.items()}
    remaining = limit - sum(allocations.values())
    # Hand the leftover budget to the largest strata first (deterministic tie-break).
    for key in sorted(strata, key=lambda k: (-len(strata[k]), k)):
        if remaining <= 0:
            break
        if allocations[key] < len(strata[key]):
            allocations[key] += 1
            remaining -= 1
    rng = np.random.default_rng(seed)
    chosen: list[int] = []
    for key, positions in strata.items():
        allocation = allocations[key]
        if allocation <= 0:
            continue
        order = np.asarray(positions, dtype=np.int64)
        rng.shuffle(order)
        chosen.extend(int(v) for v in order[:allocation].tolist())
    chosen.sort()
    return chosen


def _build_eval_dataset(config: dict[str, Any], split: str,
                        samples: int | None) -> Subset | RadioML2018Dataset:
    public = config["public_data"]
    dataset = RadioML2018Dataset(
        public["hdf5_path"], public["classes_path"], public["audit_path"],
        public["index_path"], split,
    )
    # ``samples=None`` means the full frozen split (same caliber as the epoch-log
    # metric).  A bounded budget uses a stratified (class, SNR) subset rather than
    # a prefix, so ``rated_0_20_accuracy`` stays representative of all 24 classes.
    if samples is None:
        return dataset
    limit = int(samples)
    if limit >= len(dataset):
        return dataset
    indices = _stratified_indices(
        np.asarray(dataset.labels, dtype=np.int64),
        np.asarray(dataset.snrs, dtype=np.float32),
        limit,
        int(config["seed"]),
    )
    return Subset(dataset, indices)


def evaluate_rml24(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path,
                   split: str = "validation", samples: int | None = None,
                   fake_int8: bool = False) -> dict[str, Any]:
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    device = select_device(str(config.get("device", "auto")))
    model, checkpoint = _load_model(config, checkpoint_path, fake_int8, device)
    subset = _build_eval_dataset(config, split, samples)
    loader = DataLoader(subset, batch_size=int(config["evaluation"]["batch_size"]),
                        shuffle=False, num_workers=0, collate_fn=collate_ad_amr,
                        pin_memory=device.type == "cuda")
    targets: list[int] = []
    predictions: list[int] = []
    snrs: list[float] = []
    logits: list[np.ndarray] = []
    with torch.inference_mode():
        for batch in loader:
            out, _ = model(batch["noisy_iq"].to(device, non_blocking=True))
            if not bool(torch.isfinite(out).all()):
                raise RuntimeError(f"non-finite 24-class logits in {split}")
            logits.append(out.float().cpu().numpy())
            targets.extend(batch["label"].tolist())
            predictions.extend(out.argmax(1).cpu().tolist())
            snrs.extend(float(v) for v in batch["snr_db"].tolist())
    metrics = _summary(targets, predictions, snrs, len(LABEL_ORDER_24))
    return {
        "checkpoint": str(checkpoint_path), "checkpoint_epoch": int(checkpoint["epoch"]),
        "split": split, "seed": int(config["seed"]), "samples": int(len(subset)),
        "classes": list(LABEL_ORDER_24), "metrics": metrics,
        "logits": np.concatenate(logits) if logits else np.zeros((0, 24), dtype=np.float32),
        "labels": np.asarray(targets, dtype=np.int64),
        "numeric_mode": "fake_symmetric_int8_weights_fp32_activations" if fake_int8 else "fp32",
        "final_blind_test_accessed": split == "test",
    }


def fake_int8_report_rml24(config: dict[str, Any], checkpoint_path: str | Path,
                           samples: int | None = None) -> dict[str, Any]:
    fp32 = evaluate_rml24(config, checkpoint_path, samples=samples, fake_int8=False)
    int8 = evaluate_rml24(config, checkpoint_path, samples=samples, fake_int8=True)
    fp32_acc = float(fp32["metrics"]["accuracy"])
    int8_acc = float(int8["metrics"]["accuracy"])
    fp32_cm = _confusion_matrix(fp32["labels"], fp32["logits"].argmax(1), len(LABEL_ORDER_24))
    int8_cm = _confusion_matrix(int8["labels"], int8["logits"].argmax(1), len(LABEL_ORDER_24))
    return {
        "checkpoint": str(checkpoint_path),
        "fp32_accuracy": fp32_acc,
        "fake_int8_accuracy": int8_acc,
        "accuracy_drop": fp32_acc - int8_acc,
        "fp32_per_class_recall": _per_class_recall(fp32_cm),
        "fake_int8_per_class_recall": _per_class_recall(int8_cm),
        "fp32_confusion": fp32_cm.tolist(),
        "fake_int8_confusion": int8_cm.tolist(),
        "fp32_near_qam_psk_confusion": _near_qam_psk_confusion(fp32_cm),
    }


def evaluate_rml24_channel_ood(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path,
                               samples: int | None = None, fake_int8: bool = False,
                               domains: list[str] | None = None) -> dict[str, Any]:
    """Closed-set accuracy of the 24-class model under each channel-impairment domain."""
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    device = select_device(str(config.get("device", "auto")))
    model, checkpoint = _load_model(config, checkpoint_path, fake_int8, device)
    subset = _build_eval_dataset(config, "validation", samples)
    domains_cfg = ood_channels(config.get("channel", {}))
    selected = domains or list(domains_cfg)

    results: dict[str, Any] = {}
    for name in selected:
        if name not in domains_cfg:
            raise ValueError(f"unknown channel OOD domain {name!r}")
        channel = ChannelPipeline(domains_cfg[name], RADIOML_SAMPLE_RATE_HZ)
        rng = np.random.default_rng(int(config["seed"]))
        targets: list[int] = []
        predictions: list[int] = []
        snrs: list[float] = []
        with torch.inference_mode():
            for idx in range(len(subset)):
                item = subset[idx]
                raw = item["noisy_iq"].numpy()  # [2, 1024] planar
                iq_complex = (raw[0] + 1j * raw[1]).astype(np.complex64)
                shifted, _meta = channel(iq_complex, rng, snr_db=None)
                planar = np.stack((shifted.real, shifted.imag)).astype(np.float32)
                tensor = torch.from_numpy(planar).unsqueeze(0).to(device)
                out, _ = model(tensor)
                if not bool(torch.isfinite(out).all()):
                    raise RuntimeError(f"non-finite logits under channel domain {name}")
                targets.append(int(item["label"]))
                predictions.append(int(out.argmax(1).cpu()))
                snrs.append(float(item["snr_db"]))
        results[name] = {
            "metrics": _summary(targets, predictions, snrs, len(LABEL_ORDER_24)),
            "samples": int(len(subset)),
        }
    return {
        "checkpoint": str(checkpoint_path), "checkpoint_epoch": int(checkpoint["epoch"]),
        "domains": results,
        "numeric_mode": "fake_symmetric_int8_weights_fp32_activations" if fake_int8 else "fp32",
    }
