"""Final blind test: run exactly once on the frozen ``ood_final_test`` split.

The frozen method / temperature / threshold come from the OOD-U manifest (read-
only).  This module reports the full metric set (ranking metrics, frozen-
threshold detection accuracy, ID accept / ID false-reject, OOD reject, per-SNR,
per-unknown-modulation, bootstrap 95% CI) and then marks the single-access audit
flag — premature or repeated access fails closed.
"""

from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np

from ood.metrics import (
    aupr_in, aupr_out, auroc, bootstrap_ci, fpr95,
    ood_detection_accuracy, oscr,
)
from ood.scores import compute_scores
from ood_u import contract
from ood_u.benchmark import class_indices, logits_for
from ood_u.data import SplitRecords
from ood_u.manifest import FinalTestGuard, manifest_sha256, read_ood_u_manifest
from ood_u.model import ADAMRV11Net


def _per_snr_accept_reject(accept: np.ndarray, snr: np.ndarray) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for value in sorted(set(float(s) for s in snr)):
        mask = snr == value
        out[f"{value:g}"] = {
            "count": int(mask.sum()),
            "rate": float(np.mean(accept[mask])),
        }
    return out


def _per_modulation_reject(reject: np.ndarray, modulation: np.ndarray) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for mod in sorted(set(str(m) for m in modulation)):
        mask = modulation == mod
        out[mod] = {"count": int(mask.sum()), "reject_rate": float(np.mean(reject[mask]))}
    return out


def run_blind_test(
    model: ADAMRV11Net,
    manifest_path: str | Path,
    *,
    id_test: SplitRecords,
    near_test: SplitRecords,
    far_test: SplitRecords,
    amb_test: SplitRecords,
    audit_dir: str | Path,
    run_id: str,
    n_boot: int = 1000,
) -> dict[str, Any]:
    """Run the final blind test once and mark the audit flag (fail-closed)."""
    manifest = read_ood_u_manifest(manifest_path)
    if manifest["final_test_accessed"]:
        raise RuntimeError("OOD-U manifest final_test_accessed is already true; blind test already ran")

    guard = FinalTestGuard(Path(audit_dir) / "final_test_access_audit.json")
    guard.assert_not_accessed()

    method = manifest["score_method"]
    temperature = manifest["temperature"]
    threshold = manifest["threshold"]
    wp = manifest["working_points"][manifest["target_operating_point"]]

    id_logits = logits_for(model, id_test)
    near_logits = logits_for(model, near_test)
    far_logits = logits_for(model, far_test)
    amb_logits = logits_for(model, amb_test)
    id_correct = (np.argmax(id_logits, axis=1) == class_indices(id_test))

    id_s = compute_scores(id_logits, method, temperature)
    near_s = compute_scores(near_logits, method, temperature)
    far_s = compute_scores(far_logits, method, temperature)
    amb_s = compute_scores(amb_logits, method, temperature)
    overall_s = np.concatenate([near_s, far_s])
    overall_logits = np.concatenate([near_logits, far_logits])

    def ranking(id_scores: np.ndarray, ood_scores: np.ndarray) -> dict[str, Any]:
        return {
            "auroc": auroc(id_scores, ood_scores),
            "aupr_in": aupr_in(id_scores, ood_scores),
            "aupr_out": aupr_out(id_scores, ood_scores),
            "fpr95": fpr95(id_scores, ood_scores),
            "oscr": oscr(id_scores, ood_scores, id_correct),
        }

    id_accept = id_s <= threshold
    overall_reject = overall_s > threshold

    # Bootstrap the frozen-threshold detection accuracy and the overall AUROC.
    det_acc = float(ood_detection_accuracy(id_s, overall_s, threshold))
    # Bootstrap the frozen-threshold detection accuracy with the threshold bound:
    # bootstrap_ci resamples positional arrays and calls metric_fn(*sampled), so the
    # threshold must be bound via partial (it is a fixed scalar, not a resample axis).
    det_acc_ci = bootstrap_ci(partial(ood_detection_accuracy, threshold=threshold),
                              id_s, overall_s, n_boot=n_boot, seed=contract.OOD_SEED) \
        if len(overall_s) else {"estimate": det_acc, "lower": det_acc, "upper": det_acc, "n_boot": n_boot}
    auroc_ci = bootstrap_ci(auroc, id_s, overall_s, n_boot=n_boot, seed=contract.OOD_SEED)

    report: dict[str, Any] = {
        "run_id": run_id,
        "manifest_sha256": manifest_sha256(manifest),
        "score_method": method,
        "temperature": temperature,
        "threshold": threshold,
        "working_point": manifest["target_operating_point"],
        "working_point_spec": wp,
        "id_samples": len(id_test),
        "near_samples": len(near_test),
        "far_samples": len(far_test),
        "ambiguous_samples": len(amb_test),
        "overall": ranking(id_s, overall_s),
        "near": ranking(id_s, near_s),
        "far": ranking(id_s, far_s),
        "ambiguous_side_report": ranking(id_s, amb_s),
        "ood_detection_accuracy": det_acc,
        "ood_detection_accuracy_ci95": det_acc_ci,
        "auroc_ci95": auroc_ci,
        "id_accept_rate": float(np.mean(id_accept)),
        "id_false_reject_rate": float(np.mean(id_s > threshold)),
        "ood_reject_rate": float(np.mean(overall_reject)),
        "near_reject_rate": float(np.mean(near_s > threshold)),
        "far_reject_rate": float(np.mean(far_s > threshold)),
        "id_accept_by_snr": _per_snr_accept_reject(id_accept, id_test.snr_db),
        "ood_reject_by_snr": _per_snr_accept_reject(overall_reject, np.concatenate([near_test.snr_db, far_test.snr_db])),
        "ood_reject_by_modulation": _per_modulation_reject(
            overall_reject, np.concatenate([near_test.modulation, far_test.modulation])),
    }

    # Mark accessed exactly once (fails closed on any prior access).
    guard.mark_accessed(run_id, report["manifest_sha256"])
    return report


__all__ = ["run_blind_test"]
