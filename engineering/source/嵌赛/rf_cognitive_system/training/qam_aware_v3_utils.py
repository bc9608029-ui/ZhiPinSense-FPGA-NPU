"""Configuration helpers for the independent QAM-Aware V3 track."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from training.ablation_utils import verify_baseline_contract
from training.utils import load_config, resolve_project_path


def _read_yaml(path: str | Path) -> tuple[dict[str, Any], Path]:
    resolved = resolve_project_path(path)
    data = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Configuration must be a mapping: {resolved}")
    return data, resolved


def _deep_update(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = copy.deepcopy(value)
    return target


def load_qam_aware_v3_config(path: str | Path) -> dict[str, Any]:
    """Merge the frozen baseline, V3 experiment and optional smoke overrides.

    Unlike the frozen V2 loader, V3 intentionally permits nested channel
    overrides so robustness training can add impairments without modifying the
    old baseline file.
    """

    verify_baseline_contract()
    requested, requested_path = _read_yaml(path)
    if "experiment_config" in requested:
        experiment, experiment_path = _read_yaml(requested["experiment_config"])
        overrides = {key: value for key, value in requested.items() if key != "experiment_config"}
    else:
        experiment, experiment_path, overrides = requested, requested_path, {}

    baseline = load_config(experiment.get("baseline_config", "configs/baseline.yaml"))
    merged = copy.deepcopy(baseline)
    _deep_update(merged, {key: value for key, value in experiment.items() if key != "baseline_config"})
    _deep_update(merged, overrides)
    # ``model`` is a schema boundary, not an extension of Baseline V1's model
    # dictionary.  Retaining V1-only keys (for example ``base_channels``)
    # would silently change or break the V3 constructor.
    merged["model"] = copy.deepcopy(experiment["model"])
    if isinstance(overrides.get("model"), dict):
        _deep_update(merged["model"], overrides["model"])
    merged["_experiment_path"] = str(experiment_path)
    merged["_requested_config_path"] = str(requested_path)
    merged["_baseline_path"] = str(baseline["_config_path"])

    classes = [str(name).upper() for name in merged["signal"]["modulations"]]
    expected = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]
    if classes != expected:
        raise RuntimeError(f"V3 class order changed: expected {expected}, got {classes}")
    if int(merged["signal"]["sample_length"]) != 1024:
        raise RuntimeError("V3 deployment contract requires exactly 1024 complex IQ samples")
    if int(merged["model_contract"]["physical_channels"]) != 3:
        raise RuntimeError("V3 requires [power, lag1_real, lag1_imag] physical channels")
    return merged
