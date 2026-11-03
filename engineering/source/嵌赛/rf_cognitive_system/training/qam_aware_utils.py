"""Configuration loading for QAM-Aware V2 under the frozen Baseline contract."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from training.ablation_utils import verify_baseline_contract
from training.utils import load_config, resolve_project_path


def _read_yaml(path: str | Path) -> tuple[dict[str, Any], Path]:
    resolved = resolve_project_path(path)
    return yaml.safe_load(resolved.read_text(encoding="utf-8")), resolved


def load_qam_aware_config(path: str | Path) -> dict[str, Any]:
    """Merge baseline, V2 experiment, and optional smoke overrides."""
    verify_baseline_contract()
    requested, requested_path = _read_yaml(path)
    if "experiment_config" in requested:
        experiment, experiment_path = _read_yaml(requested["experiment_config"])
        overrides = requested
    else:
        experiment, experiment_path, overrides = requested, requested_path, {}

    baseline = load_config(experiment.get("baseline_config", "configs/baseline.yaml"))
    merged = copy.deepcopy(baseline)
    for section in ("dataset", "training", "evaluation"):
        if section in experiment:
            merged[section].update(experiment[section])
        if section in overrides:
            merged[section].update(overrides[section])
    merged["qam_aware"] = copy.deepcopy(experiment["model"])
    merged["variants"] = list(experiment["variants"])
    merged["final_blind_test"] = copy.deepcopy(experiment["final_blind_test"])
    merged["output_root"] = overrides.get("output_root", experiment["output_root"])
    merged["_experiment_path"] = str(experiment_path)
    merged["_requested_config_path"] = str(requested_path)
    return merged

