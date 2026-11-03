"""Load DualDomain experiments while enforcing the frozen Baseline contract."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from training.utils import PROJECT_ROOT, load_config, resolve_project_path


def verify_baseline_contract() -> None:
    lock = json.loads((PROJECT_ROOT / "configs" / "baseline_v1_lock.json").read_text(encoding="utf-8"))
    changed = []
    for relative, expected in lock["sha256"].items():
        actual = hashlib.sha256((PROJECT_ROOT / relative).read_bytes()).hexdigest()
        if actual != expected:
            changed.append(relative)
    if changed:
        raise RuntimeError(f"Frozen Baseline V1 contract changed: {changed}")


def load_ablation_config(path: str | Path) -> dict[str, Any]:
    verify_baseline_contract()
    experiment_path = resolve_project_path(path)
    experiment = yaml.safe_load(experiment_path.read_text(encoding="utf-8"))
    baseline = load_config(experiment.get("baseline_config", "configs/baseline.yaml"))
    merged = copy.deepcopy(baseline)
    for section in ("dataset", "training", "evaluation"):
        if section in experiment:
            merged[section].update(experiment[section])
    merged["dual_domain"] = copy.deepcopy(experiment["model"])
    merged["variants"] = list(experiment.get("variants", ["time_only", "frequency_only", "dual_domain"]))
    merged["output_root"] = experiment["output_root"]
    merged["_experiment_path"] = str(experiment_path)
    return merged
