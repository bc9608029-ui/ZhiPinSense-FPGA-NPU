"""Semantic OOD evaluation (shared by the 12-class and 24-class models).

Semantic OOD means a *new modulation family* that maps to UNKNOWN.  This module
computes raw-logits anomaly scores (MSP / Entropy / MaxLogit / Energy) for ID and
synthetic OOD records, then reports the full ranking metrics (AUROC / AUPR-IN /
AUPR-OUT / FPR95 / OSCR) plus the three frozen working points (ID false-reject
and OOD false-accept rates).  Thresholds are locked on ``ood_validation`` only;
the ``ood_final_test`` family is scored exactly once and never used for locking.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import torch

from datasets.ood_dataset import OOD_FAMILIES, default_ood_signal_config, generate_ood_records
from ood.calibration import calibrate_temperature
from ood.metrics import bootstrap_ci, oscr, ranking_metrics
from ood.scores import compute_scores
from ood.thresholds import (
    decision_at_thresholds,
    id_false_reject_rate,
    ood_false_accept_rate,
    select_thresholds,
)
from training.utils import load_yaml, select_device

DEFAULT_METHODS = ("msp", "entropy", "max_logit", "energy")


def run_model_logits(model: torch.nn.Module, planar: np.ndarray,
                     device: torch.device, batch_size: int = 512) -> np.ndarray:
    """Run a logits-returning model over planar float32 [N, 2, L]."""
    planar = np.asarray(planar, dtype=np.float32)
    if planar.ndim != 3 or planar.shape[1] != 2:
        raise ValueError(f"planar must be [N, 2, L], got {planar.shape}")
    chunks: list[np.ndarray] = []
    with torch.inference_mode():
        for start in range(0, planar.shape[0], int(batch_size)):
            stop = min(start + int(batch_size), planar.shape[0])
            tensor = torch.from_numpy(planar[start:stop]).to(device)
            out = model(tensor)
            if not bool(torch.isfinite(out).all()):
                raise RuntimeError(f"non-finite OOD logits at rows {start}:{stop}")
            chunks.append(out.float().cpu().numpy())
    return np.concatenate(chunks, axis=0)


def _id_scores(method: str, logits: np.ndarray, temperature: float) -> np.ndarray:
    return compute_scores(logits, method, temperature)


def semantic_ood_report(
    model: torch.nn.Module,
    device: torch.device,
    id_logits: np.ndarray,
    id_labels: np.ndarray,
    *,
    signal_config: dict[str, Any],
    ood_seed: int,
    count_per_modulation: int,
    families: list[str],
    threshold_family: str,
    methods: tuple[str, ...] = DEFAULT_METHODS,
    temperature: float = 1.0,
    n_boot: int = 500,
    include_ambiguous: bool = False,
    batch_size: int = 512,
) -> dict[str, Any]:
    """Compute the semantic OOD report for an already-loaded model."""
    id_logits = np.asarray(id_logits, dtype=np.float64)
    id_labels = np.asarray(id_labels, dtype=np.int64)
    if id_logits.ndim != 2 or id_labels.shape[0] != id_logits.shape[0]:
        raise ValueError("id_logits [N,C] and id_labels [N] must match")
    if threshold_family not in OOD_FAMILIES:
        raise ValueError(f"unknown threshold family {threshold_family!r}")

    id_correct = (id_logits.argmax(axis=1) == id_labels)

    # Lock thresholds on the frozen threshold family from ood_validation only.
    threshold_records = generate_ood_records(
        threshold_family, "ood_validation", seed=ood_seed,
        count_per_modulation=count_per_modulation, signal_config=signal_config,
    )
    threshold_logits = run_model_logits(model, threshold_records.planar, device, batch_size)

    calibrated_temperature = float(temperature)
    if "energy" in methods:
        calibrated_temperature = calibrate_temperature(id_logits, id_labels, init_temp=temperature)

    report: dict[str, Any] = {
        "id_samples": int(id_logits.shape[0]),
        "id_labels": id_labels.tolist(),
        "threshold_family": threshold_family,
        "threshold_lock_split": "ood_validation",
        "calibrated_temperature": calibrated_temperature,
        "families": {},
        "ambiguous": None,
    }

    for method in methods:
        id_scores = _id_scores(method, id_logits, calibrated_temperature)
        threshold_scores = _id_scores(method, threshold_logits, calibrated_temperature)
        locked = select_thresholds(id_scores, threshold_scores)
        report["families"][method] = {"thresholds": locked, "families": {}}
        for family in families:
            if family not in OOD_FAMILIES:
                raise ValueError(f"unknown OOD family {family!r}")
            records = generate_ood_records(
                family, "ood_final_test", seed=ood_seed,
                count_per_modulation=count_per_modulation, signal_config=signal_config,
            )
            ood_logits = run_model_logits(model, records.planar, device, batch_size)
            ood_scores = _id_scores(method, ood_logits, calibrated_temperature)
            ranking = ranking_metrics(id_scores, ood_scores)
            cinterval = {
                "auroc": bootstrap_ci(lambda a, b: ranking_metrics(a, b)["auroc"],
                                      id_scores, ood_scores, n_boot=n_boot, seed=ood_seed),
            }
            oscr_result = oscr(id_scores, ood_scores, id_correct)
            decisions = decision_at_thresholds(ood_scores, locked)
            working_points: dict[str, dict[str, float]] = {}
            for name, spec in locked.items():
                working_points[name] = {
                    "threshold": spec["threshold"],
                    "id_frr": id_false_reject_rate(id_scores, spec["threshold"]),
                    "ood_far": ood_false_accept_rate(ood_scores, spec["threshold"]),
                    "ood_rejected_fraction": float(np.mean(ood_scores > spec["threshold"])),
                }
            report["families"][method]["families"][family] = {
                "ood_samples": int(ood_logits.shape[0]),
                "modulations": list(OOD_FAMILIES[family]),
                "ranking": ranking,
                "auroc_ci": cinterval["auroc"],
                "oscr": {"auc_ccr_fpr": oscr_result["auc_ccr_fpr"]},
                "working_points": working_points,
                "decisions": {name: arr.tolist() for name, arr in decisions.items()},
                "ood_scores": ood_scores.tolist(),
            }

    if include_ambiguous:
        amb_records = generate_ood_records(
            "ambiguous", "ood_final_test", seed=ood_seed,
            count_per_modulation=count_per_modulation, signal_config=signal_config,
        )
        amb_logits = run_model_logits(model, amb_records.planar, device, batch_size)
        report["ambiguous"] = {
            "modulations": list(OOD_FAMILIES["ambiguous"]),
            "samples": int(amb_logits.shape[0]),
            "excluded_from_main_metrics": True,
            "energy_auroc": ranking_metrics(
                _id_scores("energy", id_logits, calibrated_temperature),
                _id_scores("energy", amb_logits, calibrated_temperature),
            )["auroc"],
        }

    return report


def evaluate_ood_rml24(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path,
                       *, id_split: str = "test", ood_seed: int | None = None,
                       count_per_modulation: int = 256, methods: tuple[str, ...] = DEFAULT_METHODS,
                       temperature: float = 1.0, samples: int | None = None,
                       include_ambiguous: bool = True) -> dict[str, Any]:
    """Semantic OOD evaluation for the strict 24-class model (ID = RadioML test)."""
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    device = select_device(str(config.get("device", "auto")))

    from contracts.rml24_contract import LABEL_ORDER_24
    from evaluation.evaluate_rml24 import evaluate_rml24
    from models.rml24_net import RML24Classifier, build_rml24_model

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if list(checkpoint.get("class_names", [])) != list(LABEL_ORDER_24):
        raise RuntimeError("24-class checkpoint class order differs from the frozen contract")
    model = build_rml24_model(len(LABEL_ORDER_24), **config["model"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    classifier = RML24Classifier(model).to(device).eval()

    id_result = evaluate_rml24(config, checkpoint_path, split=id_split, samples=samples)
    id_logits = id_result["logits"].astype(np.float64)
    id_labels = id_result["labels"].astype(np.int64)

    signal_config = dict(config.get("signal", default_ood_signal_config()))
    report = semantic_ood_report(
        classifier, device, id_logits, id_labels,
        signal_config=signal_config,
        ood_seed=int(ood_seed or config["seed"]),
        count_per_modulation=count_per_modulation,
        families=["near_24", "far"], threshold_family="far",
        methods=methods, temperature=temperature, include_ambiguous=include_ambiguous,
    )
    report["checkpoint"] = str(checkpoint_path)
    report["checkpoint_epoch"] = int(checkpoint["epoch"])
    report["id_split"] = id_split
    report["model"] = "RML2018_24"
    report["domain_gap_note"] = (
        "ID is real RadioML2018.01A (200 kHz); OOD is synthetic at the generator's "
        "native rate (128 kHz). A residual ID<->synthetic domain gap is possible and "
        "is reported separately, never silently merged into the OOD metric."
    )
    return report


def evaluate_ood_12class(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path,
                         **kwargs: Any) -> dict[str, Any]:
    """Semantic OOD evaluation for the 12-class model (fail-closed until the V2 checkpoint lands)."""
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    import json
    contract = json.loads(Path(config.get("_twelve_class_contract",
                           "contracts/12class_import_contract.json")).read_text(encoding="utf-8"))
    if str(contract.get("checkpoint_path", "")).startswith("PENDING") or \
            str(contract.get("model_sha256", "")).startswith("PENDING"):
        raise RuntimeError(
            "BLOCKED_12CLASS_CONTRACT: the 12-class V2 checkpoint path/SHA are still PENDING; "
            "the 12-class OOD evaluation cannot run yet."
        )
    # Wired for the 12-class model (synthetic ID space); active only after the
    # 12-class V2 checkpoint is imported with a matching SHA and label order.
    raise NotImplementedError("12-class semantic OOD runs after the 12-class V2 checkpoint is imported")


__all__ = [
    "run_model_logits", "semantic_ood_report", "evaluate_ood_rml24", "evaluate_ood_12class",
    "DEFAULT_METHODS",
]
