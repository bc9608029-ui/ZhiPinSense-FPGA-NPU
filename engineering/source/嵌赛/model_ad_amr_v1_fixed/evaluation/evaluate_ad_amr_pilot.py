"""Leakage-safe, paired AD-AMR versus frozen-V2 pilot evaluation.

Both models see the exact same generated records.  Only validation namespaces are
accepted; test and blind namespaces are rejected.  This module is deliberately
separate from the final evaluator so model selection cannot accidentally touch a
test split.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader

from datasets.ad_amr_dataset import ADAMRPairDataset, collate_ad_amr
from models.ad_amr_net import build_ad_amr_model
from models.qam_aware_rfnet import build_qam_aware_model
from training.metrics import classification_metrics, qam_mean


def _assert_selection_split(split: str) -> None:
    lowered = split.lower()
    if "validation" not in lowered or "test" in lowered or "blind" in lowered:
        raise RuntimeError(f"pilot selection may only use validation namespaces, got {split!r}")


def _load_v2(path: str | Path, num_classes: int, device: torch.device) -> torch.nn.Module:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    state = checkpoint.get("model_state")
    if not isinstance(state, dict) or len(state) != 91:
        raise RuntimeError("Frozen V2 checkpoint does not contain the expected 91-key model_state.")
    config = checkpoint.get("config", {}).get("qam_aware")
    if not isinstance(config, dict):
        raise RuntimeError("Frozen V2 checkpoint is missing config.qam_aware.")
    model = build_qam_aware_model("time_power_phase", num_classes, **config)
    model.load_state_dict(state, strict=True)
    return model.to(device).eval()


def _summarize(targets: list[int], predictions: list[int], snrs: list[float],
               classes: list[str]) -> dict[str, Any]:
    metrics = classification_metrics(targets, predictions, len(classes))
    per_class = [float(v) for v in metrics["per_class_accuracy"]]
    per_snr: dict[str, float] = {}
    for value in sorted(set(snrs)):
        selected = [p == t for p, t, snr in zip(predictions, targets, snrs) if snr == value]
        per_snr[f"{value:.0f}"] = float(sum(selected) / len(selected))
    slice_0_10 = [p == t for p, t, snr in zip(predictions, targets, snrs) if 0.0 <= snr <= 10.0]
    return {
        "accuracy": float(metrics["accuracy"]),
        "macro_f1": float(metrics["macro_f1"]),
        "cohen_kappa": float(metrics["cohen_kappa"]),
        "qam_mean_accuracy": qam_mean(per_class, classes),
        "accuracy_0_10db": (
            float(sum(slice_0_10) / len(slice_0_10)) if slice_0_10 else float("nan")
        ),
        "per_class_accuracy": {name: per_class[i] for i, name in enumerate(classes)},
        "per_snr_accuracy": per_snr,
        "confusion_matrix": metrics["confusion_matrix"],
    }


def evaluate_paired(
    config: dict[str, Any],
    candidate_checkpoint: str | Path,
    *,
    split: str = "ad_amr_validation",
    channel_config: dict[str, Any] | None = None,
    samples: int | None = None,
) -> dict[str, Any]:
    """Evaluate a candidate and V2 on one identical validation dataset."""
    _assert_selection_split(split)
    device_name = config.get("device", "auto")
    device = torch.device(
        "cuda:0" if device_name == "auto" and torch.cuda.is_available() else
        "cpu" if device_name == "auto" else device_name
    )
    classes = [str(name).upper() for name in config["signal"]["modulations"]]
    candidate_state = torch.load(candidate_checkpoint, map_location="cpu", weights_only=False)
    candidate = build_ad_amr_model(len(classes), **config["model"])
    candidate.load_state_dict(candidate_state["model_state"], strict=True)
    candidate = candidate.to(device).eval()
    baseline = _load_v2(config["v2_checkpoint"], len(classes), device)

    dataset_cfg = config["dataset"]
    count = int(samples if samples is not None else dataset_cfg["val_samples"])
    snr_values = [float(v) for v in dataset_cfg["snr_values"]]
    dataset = ADAMRPairDataset(
        count,
        config["signal"],
        channel_config if channel_config is not None else config["channel"],
        int(config["seed"]),
        split,
        snr_values=snr_values,
    )
    loader = DataLoader(
        dataset,
        batch_size=int(config["evaluation"]["batch_size"]),
        shuffle=False,
        num_workers=0,
        collate_fn=collate_ad_amr,
        pin_memory=device.type == "cuda",
    )

    targets: list[int] = []
    snrs: list[float] = []
    candidate_predictions: list[int] = []
    baseline_predictions: list[int] = []
    sample_ids: list[int] = []
    with torch.inference_mode():
        for batch in loader:
            noisy = batch["noisy_iq"].to(device, non_blocking=True)
            candidate_logits, _ = candidate(noisy)
            baseline_logits = baseline(noisy)
            if not torch.isfinite(candidate_logits).all() or not torch.isfinite(baseline_logits).all():
                raise RuntimeError(f"non-finite logits in paired pilot evaluation {split!r}")
            candidate_predictions.extend(candidate_logits.argmax(1).cpu().tolist())
            baseline_predictions.extend(baseline_logits.argmax(1).cpu().tolist())
            targets.extend(batch["label"].tolist())
            snrs.extend(float(v) for v in batch["snr_db"].tolist())
            sample_ids.extend(int(v) for v in batch["sample_id"].tolist())

    ids_bytes = np.asarray(sample_ids, dtype=np.int64).tobytes()
    return {
        "split": split,
        "seed": int(config["seed"]),
        "samples": len(targets),
        "sample_ids_sha256": hashlib.sha256(ids_bytes).hexdigest(),
        "candidate": _summarize(targets, candidate_predictions, snrs, classes),
        "v2": _summarize(targets, baseline_predictions, snrs, classes),
        "final_blind_test_accessed": False,
    }


def ood_channel_configs(base: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Fixed, validation-only channel battery used identically for V2/candidate."""
    effect_names = (
        "rayleigh", "rician", "multipath", "cfo", "phase_offset", "phase_noise", "sfo",
        "iq_imbalance", "dc_offset", "amplitude_scaling", "clipping",
        "narrowband_interference", "burst_interference",
    )

    def clean() -> dict[str, Any]:
        cfg = copy.deepcopy(base)
        cfg["domain_randomization"] = False
        for name in effect_names:
            if name in cfg:
                cfg[name]["enabled"] = False
                cfg[name]["probability"] = 0.0
        cfg.setdefault("awgn", {})["enabled"] = True
        cfg["awgn"]["probability"] = 1.0
        return cfg

    specs: dict[str, dict[str, dict[str, Any]]] = {
        "cfo_strong": {"cfo": {"hz": [-2400.0, 2400.0]}},
        "sfo": {"sfo": {"ppm": [-120.0, 120.0]}},
        "phase_noise": {"phase_noise": {"std_rad": [0.004, 0.012]}},
        "iq_imbalance": {"iq_imbalance": {"gain_db": [-2.0, 2.0], "phase_deg": [-10.0, 10.0]}},
        "rayleigh": {"rayleigh": {}},
        "rician": {"rician": {"k_factor": [1.0, 5.0]}},
        "multipath": {"multipath": {"num_taps": [3, 6], "max_delay": 20}},
        "clipping": {"clipping": {"level_rms": [0.8, 1.5]}},
        "multi_impairment": {
            "cfo": {"hz": [-1800.0, 1800.0]},
            "phase_noise": {"std_rad": [0.002, 0.008]},
            "iq_imbalance": {"gain_db": [-1.5, 1.5], "phase_deg": [-8.0, 8.0]},
            "multipath": {"num_taps": [2, 5], "max_delay": 16},
        },
    }
    result: dict[str, dict[str, Any]] = {}
    for domain, effects in specs.items():
        cfg = clean()
        for name, overrides in effects.items():
            cfg.setdefault(name, {}).update(overrides)
            cfg[name]["enabled"] = True
            cfg[name]["probability"] = 1.0
        result[domain] = cfg
    return result
