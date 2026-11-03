"""Configuration helpers for the independent QAM-Aware V3.3 track.

V3.3 reuses the frozen baseline merge and contract checks (class order, 1024
sample frame, 3 physical channels) from the shared ablation loader.  The loader
is track-agnostic and reads everything from the requested YAML path.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from training.ablation_utils import verify_baseline_contract
from training.utils import load_config, resolve_project_path

EXPECTED_CLASSES = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]


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


def load_qam_aware_v3_3_config(path: str | Path) -> dict[str, Any]:
    """Merge the frozen baseline, V3.3 experiment and optional override files.

    The merge is deliberately single-level for the override chain but permits
    nested channel/training overrides (robustness training), exactly like V3.
    ``model`` is a schema boundary, not an extension of Baseline V1's model
    dictionary, so V1-only keys never leak into the V3.3 constructor.
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
    merged["model"] = copy.deepcopy(experiment["model"])
    if isinstance(overrides.get("model"), dict):
        _deep_update(merged["model"], overrides["model"])
    merged["_experiment_path"] = str(experiment_path)
    merged["_requested_config_path"] = str(requested_path)
    merged["_baseline_path"] = str(baseline["_config_path"])

    classes = [str(name).upper() for name in merged["signal"]["modulations"]]
    if classes != EXPECTED_CLASSES:
        raise RuntimeError(f"V3.3 class order changed: expected {EXPECTED_CLASSES}, got {classes}")
    if int(merged["signal"]["sample_length"]) != 1024:
        raise RuntimeError("V3.3 deployment contract requires exactly 1024 complex IQ samples")
    if int(merged["model_contract"]["physical_channels"]) != 3:
        raise RuntimeError("V3.3 requires [power, lag1_real, lag1_imag] physical channels")
    return merged


def write_text_lf(path: str | Path, text: str) -> Path:
    """Write text with explicit LF line endings (no CRLF, no BOM).

    ``Path.write_text`` opens in text mode with ``newline=None``, which on
    Windows translates ``\\n`` to ``\\r\\n`` and corrupts sha256 manifests and
    shell scripts consumed on Linux.  Kept here (not in the frozen
    ``training.utils``) to avoid mutating a locked Baseline V1 asset.
    """

    destination = resolve_project_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return destination
