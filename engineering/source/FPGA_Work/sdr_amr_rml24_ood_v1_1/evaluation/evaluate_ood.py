"""Semantic OOD evaluation (shared by the 12-class and 24-class models).

Semantic OOD means a *new modulation family* that maps to UNKNOWN.  This module
computes raw-logits anomaly scores (MSP / Entropy / MaxLogit / Energy) for ID and
synthetic OOD records, then reports the full ranking metrics (AUROC / AUPR-IN /
AUPR-OUT / FPR95 / OSCR) plus the three frozen working points (ID false-reject
and OOD false-accept rates).

The evaluation is split into two strictly separated phases:

* **Calibration** (``calibrate_ood_thresholds`` / ``evaluate_ood_rml24``) — locks
  the Energy temperature and the three working-point thresholds on ID *validation*
  and ``ood_validation`` only.  It also reports, per method (MSP / Entropy /
  MaxLogit / Energy), the full ranking metrics (AUROC / AUPR-IN / AUPR-OUT /
  FPR@95TPR / OSCR), bootstrap 95% CIs, and the working-point ID FRR / accept and
  OOD FAR / reject rates, then derives a validation-only ``recommended_score_method``.
  It never instantiates the ``test`` split nor the ``ood_final_test`` family.
* **Final scoring** (``score_ood_final`` / ``evaluate_ood_final_rml24``) — reads the
  frozen threshold manifest and scores ``ood_final_test`` exactly once with the
  frozen score method / temperature / thresholds.  It never re-fits the
  temperature and never re-selects thresholds.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
import torch

from datasets.ood_dataset import OOD_FAMILIES, default_ood_signal_config, generate_ood_records
from ood.calibration import calibrate_temperature
from ood.method_selection import select_score_method
from ood.metrics import bootstrap_ci, oscr, ranking_metrics
from ood.scores import compute_scores
from ood.threshold_manifest import SCORE_METHODS, read_threshold_manifest
from ood.thresholds import (
    decision_at_thresholds,
    id_false_reject_rate,
    ood_false_accept_rate,
    select_thresholds,
)
from training.utils import load_yaml, select_device

DEFAULT_METHODS = ("msp", "entropy", "max_logit", "energy")

# The semantic OOD families scored once at *final* evaluation.  ``far`` is the
# threshold family locked on ``ood_validation`` at calibration; ``near_24`` +
# ``far`` are the final-scoring families read from ``ood_final_test`` once.
FINAL_FAMILIES = ("near_24", "far")


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


def _load_rml24_classifier(config: dict[str, Any], checkpoint_path: str | Path) -> tuple[torch.nn.Module, dict[str, Any]]:
    """Load the frozen 24-class checkpoint and wrap it in the logits classifier."""
    from contracts.rml24_contract import LABEL_ORDER_24
    from models.rml24_net import RML24Classifier, build_rml24_model

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    if list(checkpoint.get("class_names", [])) != list(LABEL_ORDER_24):
        raise RuntimeError("24-class checkpoint class order differs from the frozen contract")
    model = build_rml24_model(len(LABEL_ORDER_24), **config["model"])
    model.load_state_dict(checkpoint["model_state"], strict=True)
    return RML24Classifier(model), checkpoint


def calibrate_ood_thresholds(
    model: torch.nn.Module,
    device: torch.device,
    id_logits: np.ndarray,
    id_labels: np.ndarray,
    *,
    signal_config: dict[str, Any],
    ood_seed: int,
    count_per_modulation: int,
    threshold_family: str,
    methods: tuple[str, ...] = DEFAULT_METHODS,
    temperature: float = 1.0,
    batch_size: int = 512,
    n_boot: int = 1000,
    target_operating_point: str = "balanced",
) -> dict[str, Any]:
    """Phase A: lock temperature + thresholds on ID validation + ``ood_validation``.

    Never instantiates ``test`` or ``ood_final_test``; the only OOD split touched
    here is ``ood_validation`` for the frozen threshold family.  For each method it
    also reports the full ranking metrics (AUROC / AUPR-IN / AUPR-OUT / FPR@95TPR /
    OSCR), bootstrap 95% CIs, and the three working points with ID FRR / accept rate
    and OOD FAR / reject rate, then derives a validation-only ``recommended_score_method``
    via a deterministic composite ranking (see ``ood.method_selection``).
    """
    id_logits = np.asarray(id_logits, dtype=np.float64)
    id_labels = np.asarray(id_labels, dtype=np.int64)
    if id_logits.ndim != 2 or id_labels.shape[0] != id_logits.shape[0]:
        raise ValueError("id_logits [N,C] and id_labels [N] must match")
    if threshold_family not in OOD_FAMILIES:
        raise ValueError(f"unknown threshold family {threshold_family!r}")

    threshold_records = generate_ood_records(
        threshold_family, "ood_validation", seed=ood_seed,
        count_per_modulation=count_per_modulation, signal_config=signal_config,
    )
    threshold_logits = run_model_logits(model, threshold_records.planar, device, batch_size)

    calibrated_temperature = float(temperature)
    if "energy" in methods:
        calibrated_temperature = calibrate_temperature(id_logits, id_labels, init_temp=temperature)

    id_correct = (id_logits.argmax(axis=1) == id_labels)

    families: dict[str, Any] = {}
    for method in methods:
        id_scores = _id_scores(method, id_logits, calibrated_temperature)
        threshold_scores = _id_scores(method, threshold_logits, calibrated_temperature)
        locked = select_thresholds(id_scores, threshold_scores)
        ranking = ranking_metrics(id_scores, threshold_scores)
        auroc_ci = bootstrap_ci(
            lambda a, b: ranking_metrics(a, b)["auroc"],
            id_scores, threshold_scores, n_boot=int(n_boot), seed=int(ood_seed))
        fpr95_ci = bootstrap_ci(
            lambda a, b: ranking_metrics(a, b)["fpr95"],
            id_scores, threshold_scores, n_boot=int(n_boot), seed=int(ood_seed))
        oscr_result = oscr(id_scores, threshold_scores, id_correct)
        working_points: dict[str, dict[str, float]] = {}
        for name, spec in locked.items():
            working_points[name] = {
                "threshold": float(spec["threshold"]),
                "id_frr": float(spec["id_frr"]),
                "id_accept_rate": 1.0 - float(spec["id_frr"]),
                "ood_far": float(spec["ood_far"]),
                "ood_rejected_fraction": float(np.mean(threshold_scores > spec["threshold"])),
            }
        families[method] = {
            "thresholds": locked,
            "ranking": ranking,
            "auroc_ci": auroc_ci,
            "fpr95_ci": fpr95_ci,
            "oscr": {"auc_ccr_fpr": oscr_result["auc_ccr_fpr"]},
            "working_points": working_points,
            "calibration_samples": {
                "id": int(id_logits.shape[0]),
                "ood": int(threshold_logits.shape[0]),
            },
        }

    selection = select_score_method(families, target_operating_point=target_operating_point)

    return {
        "id_samples": int(id_logits.shape[0]),
        "threshold_family": threshold_family,
        "threshold_lock_split": "ood_validation",
        "calibrated_temperature": calibrated_temperature,
        "families": families,
        "recommended_score_method": selection["recommended_score_method"],
        "method_selection": selection,
    }


def score_ood_final(
    model: torch.nn.Module,
    device: torch.device,
    id_logits: np.ndarray,
    id_labels: np.ndarray,
    *,
    score_method: str,
    temperature: float,
    thresholds: dict[str, dict[str, float]],
    signal_config: dict[str, Any],
    ood_seed: int,
    count_per_modulation: int,
    families: list[str],
    n_boot: int = 500,
    batch_size: int = 512,
) -> dict[str, Any]:
    """Phase B: score ``ood_final_test`` once with *frozen* thresholds.

    ``score_method`` / ``temperature`` / ``thresholds`` must come from the frozen
    threshold manifest; this function never re-fits the temperature and never
    re-selects thresholds.
    """
    id_logits = np.asarray(id_logits, dtype=np.float64)
    id_labels = np.asarray(id_labels, dtype=np.int64)
    if id_logits.ndim != 2 or id_labels.shape[0] != id_logits.shape[0]:
        raise ValueError("id_logits [N,C] and id_labels [N] must match")
    if score_method not in SCORE_METHODS:
        raise ValueError(f"unknown score method {score_method!r}")

    id_correct = (id_logits.argmax(axis=1) == id_labels)
    id_scores = _id_scores(score_method, id_logits, float(temperature))

    node: dict[str, Any] = {"thresholds": thresholds, "families": {}}
    for family in families:
        if family not in OOD_FAMILIES:
            raise ValueError(f"unknown OOD family {family!r}")
        records = generate_ood_records(
            family, "ood_final_test", seed=ood_seed,
            count_per_modulation=count_per_modulation, signal_config=signal_config,
        )
        ood_logits = run_model_logits(model, records.planar, device, batch_size)
        ood_scores = _id_scores(score_method, ood_logits, float(temperature))
        ranking = ranking_metrics(id_scores, ood_scores)
        cinterval = {
            "auroc": bootstrap_ci(lambda a, b: ranking_metrics(a, b)["auroc"],
                                  id_scores, ood_scores, n_boot=n_boot, seed=ood_seed),
        }
        oscr_result = oscr(id_scores, ood_scores, id_correct)
        decisions = decision_at_thresholds(ood_scores, thresholds)
        working_points: dict[str, dict[str, float]] = {}
        for name, spec in thresholds.items():
            working_points[name] = {
                "threshold": float(spec["threshold"]),
                "id_frr": id_false_reject_rate(id_scores, spec["threshold"]),
                "ood_far": ood_false_accept_rate(ood_scores, spec["threshold"]),
                "ood_rejected_fraction": float(np.mean(ood_scores > spec["threshold"])),
            }
        node["families"][family] = {
            "ood_samples": int(ood_logits.shape[0]),
            "modulations": list(OOD_FAMILIES[family]),
            "ranking": ranking,
            "auroc_ci": cinterval["auroc"],
            "oscr": {"auc_ccr_fpr": oscr_result["auc_ccr_fpr"]},
            "working_points": working_points,
            "decisions": {name: arr.tolist() for name, arr in decisions.items()},
            "ood_scores": ood_scores.tolist(),
        }

    return {
        "id_samples": int(id_logits.shape[0]),
        "score_method": score_method,
        "temperature": float(temperature),
        "thresholds": thresholds,
        "families": {score_method: node},
    }


def evaluate_ood_rml24(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path,
                       *, id_split: str = "validation", ood_seed: int | None = None,
                       count_per_modulation: int = 256, methods: tuple[str, ...] = DEFAULT_METHODS,
                       temperature: float = 1.0, samples: int | None = None) -> dict[str, Any]:
    """Phase A (calibration) for the 24-class model — ID = RadioML *validation*.

    Locks the temperature and working points on ``ood_validation`` only; the ID
    split defaults to ``validation`` so neither ``test`` nor ``ood_final_test`` is
    ever touched here.
    """
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    device = select_device(str(config.get("device", "auto")))

    from evaluation.evaluate_rml24 import evaluate_rml24

    classifier, checkpoint = _load_rml24_classifier(config, checkpoint_path)
    classifier = classifier.to(device).eval()

    id_result = evaluate_rml24(config, checkpoint_path, split=id_split, samples=samples)
    id_logits = id_result["logits"].astype(np.float64)
    id_labels = id_result["labels"].astype(np.int64)

    signal_config = dict(config.get("signal", default_ood_signal_config()))
    report = calibrate_ood_thresholds(
        classifier, device, id_logits, id_labels,
        signal_config=signal_config,
        ood_seed=int(ood_seed or config["seed"]),
        count_per_modulation=count_per_modulation,
        threshold_family="far",
        methods=methods, temperature=temperature,
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


def evaluate_ood_final_rml24(config_or_path: dict[str, Any] | str, checkpoint_path: str | Path,
                             threshold_manifest_path: str | Path, *,
                             id_result: dict[str, Any],
                             ood_seed: int | None = None,
                             count_per_modulation: int = 256,
                             families: tuple[str, ...] = FINAL_FAMILIES) -> dict[str, Any]:
    """Phase B (final) for the 24-class model — frozen thresholds, ``ood_final_test``.

    ``id_result`` must be the already-computed ``evaluate_rml24(split="test")``
    result; its logits/labels/metrics are reused verbatim so the ID test split is
    inferred exactly once across the whole final flow.  The frozen threshold
    manifest supplies the score method / temperature / thresholds, so nothing is
    re-fit and no threshold is re-selected here.
    """
    config = copy.deepcopy(config_or_path) if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    device = select_device(str(config.get("device", "auto")))

    classifier, checkpoint = _load_rml24_classifier(config, checkpoint_path)
    classifier = classifier.to(device).eval()

    manifest = read_threshold_manifest(threshold_manifest_path)

    id_logits = np.asarray(id_result["logits"], dtype=np.float64)
    id_labels = np.asarray(id_result["labels"], dtype=np.int64)

    signal_config = dict(config.get("signal", default_ood_signal_config()))
    report = score_ood_final(
        classifier, device, id_logits, id_labels,
        score_method=manifest["score_method"],
        temperature=manifest["temperature"],
        thresholds=manifest["thresholds"],
        signal_config=signal_config,
        ood_seed=int(ood_seed or config["seed"]),
        count_per_modulation=count_per_modulation,
        families=list(families),
    )
    report["checkpoint"] = str(checkpoint_path)
    report["checkpoint_epoch"] = int(checkpoint["epoch"])
    report["id_split"] = "test"
    report["model"] = "RML2018_24"
    report["threshold_manifest"] = str(threshold_manifest_path)
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
    "run_model_logits", "calibrate_ood_thresholds", "score_ood_final",
    "evaluate_ood_rml24", "evaluate_ood_final_rml24", "evaluate_ood_12class",
    "DEFAULT_METHODS", "FINAL_FAMILIES",
]
