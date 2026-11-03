"""Regression tests for the validation-only OOD method selection (errata 1).

Calibration now reports, per score method (MSP / Entropy / MaxLogit / Energy), the
full ranking metrics on ``ood_validation`` plus a deterministic composite ranking
that recommends a single method — without ever touching ``test`` / ``ood_final_test``.
All tests are offline (no HDF5 / no model / no checkpoint).
"""

from __future__ import annotations

import inspect
import json

import numpy as np
import pytest

from ood.method_selection import (
    require_complete_method_metrics,
    select_score_method,
)
from ood.metrics import bootstrap_ci, oscr, ranking_metrics
from ood.thresholds import select_thresholds


class _Rec:
    def __init__(self) -> None:
        self.planar = np.zeros((16, 2, 1024), dtype=np.float32)


def _ood_logits() -> np.ndarray:
    return np.random.default_rng(7).normal(size=(16, 24)).astype(np.float32)


def _fake_id(n: int = 64, c: int = 24) -> tuple[np.ndarray, np.ndarray]:
    logits = np.full((n, c), -5.0, dtype=np.float64)
    labels = np.arange(n) % c
    logits[np.arange(n), labels] = 5.0
    return logits, labels.astype(np.int64)


def _method_node(id_scores: np.ndarray, ood_scores: np.ndarray,
                 id_correct: np.ndarray, seed: int = 7) -> dict:
    locked = select_thresholds(id_scores, ood_scores)
    working_points: dict = {}
    for name, spec in locked.items():
        working_points[name] = {
            "threshold": float(spec["threshold"]),
            "id_frr": float(spec["id_frr"]),
            "id_accept_rate": 1.0 - float(spec["id_frr"]),
            "ood_far": float(spec["ood_far"]),
            "ood_rejected_fraction": float(np.mean(ood_scores > spec["threshold"])),
        }
    return {
        "thresholds": locked,
        "ranking": ranking_metrics(id_scores, ood_scores),
        "auroc_ci": bootstrap_ci(lambda a, b: ranking_metrics(a, b)["auroc"],
                                 id_scores, ood_scores, n_boot=20, seed=seed),
        "fpr95_ci": bootstrap_ci(lambda a, b: ranking_metrics(a, b)["fpr95"],
                                 id_scores, ood_scores, n_boot=20, seed=seed),
        "oscr": {"auc_ccr_fpr": oscr(id_scores, ood_scores, id_correct)["auc_ccr_fpr"]},
        "working_points": working_points,
        "calibration_samples": {"id": len(id_scores), "ood": len(ood_scores)},
    }


def _families(shift: bool = False) -> dict:
    """Four complete method nodes from synthetic, well-separated ID/OOD scores.

    With ``shift=True`` each successive method gets increasingly higher OOD scores,
    so ``energy`` (last) has the clearest ID/OOD separation and wins the ranking.
    """
    rng = np.random.default_rng(2026)
    id_scores = rng.normal(0.0, 0.5, 256)
    base_ood = rng.normal(2.0, 0.5, 256)
    id_correct = np.ones(256, dtype=bool)
    families: dict = {}
    for i, method in enumerate(("msp", "entropy", "max_logit", "energy")):
        ood_scores = base_ood + (0.3 * i if shift else 0.0)
        families[method] = _method_node(id_scores, ood_scores, id_correct, seed=7 + i)
    return families


def _freeze_inputs(tmp_path, families: dict) -> tuple[str, str]:
    report = {"rml24": {
        "id_samples": 256,
        "threshold_family": "far",
        "threshold_lock_split": "ood_validation",
        "calibrated_temperature": 1.0,
        "families": families,
        # Not read by freeze_thresholds (it recomputes from `families`), but kept
        # to mirror the real calibration report shape.
        "recommended_score_method": "energy",
    }}
    final = {"checkpoint_sha256": "b" * 64, "dataset_sha256": "c" * 64}
    report_path = tmp_path / "ood_baselines.json"
    final_path = tmp_path / "final_checkpoint_manifest.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    final_path.write_text(json.dumps(final), encoding="utf-8")
    return str(final_path), str(report_path)


def _patch_freeze(monkeypatch, rft) -> None:
    monkeypatch.setattr(rft, "label_contract_sha256", lambda: "a" * 64)
    monkeypatch.setattr(rft, "OOD_FAMILIES", {"far": ["m1", "m2", "m3", "m4", "m5"]})


def test_calibration_reports_complete_metrics_for_all_methods(monkeypatch):
    from evaluation import evaluate_ood as eo

    monkeypatch.setattr(eo, "generate_ood_records", lambda family, split, **kw: _Rec())
    monkeypatch.setattr(eo, "run_model_logits", lambda m, p, d, bs: _ood_logits())
    id_logits, id_labels = _fake_id()

    report = eo.calibrate_ood_thresholds(
        None, None, id_logits, id_labels,
        signal_config={}, ood_seed=3407, count_per_modulation=256,
        threshold_family="far", n_boot=50,
    )
    for method in eo.DEFAULT_METHODS:
        node = report["families"][method]
        for key in ("auroc", "aupr_in", "aupr_out", "fpr95"):
            assert np.isfinite(node["ranking"][key]), f"{method}.ranking.{key} not finite"
        assert np.isfinite(node["oscr"]["auc_ccr_fpr"])
        assert np.isfinite(node["auroc_ci"]["estimate"])
        assert np.isfinite(node["fpr95_ci"]["estimate"])
        assert set(node["thresholds"]) == {"conservative", "balanced", "strict"}
        for name in ("conservative", "balanced", "strict"):
            wp = node["working_points"][name]
            for k in ("threshold", "id_frr", "id_accept_rate", "ood_far", "ood_rejected_fraction"):
                assert np.isfinite(wp[k]), f"{method}.working_points.{name}.{k} not finite"
    assert report["recommended_score_method"] in eo.DEFAULT_METHODS
    assert report["method_selection"]["validation_only"] is True
    assert report["method_selection"]["final_data_used"] is False


def test_calibration_never_constructs_test_or_ood_final_test(monkeypatch):
    from evaluation import evaluate_ood as eo

    splits: list[str] = []
    monkeypatch.setattr(
        eo, "generate_ood_records",
        lambda family, split, **kw: splits.append(split) or _Rec())
    monkeypatch.setattr(eo, "run_model_logits", lambda m, p, d, bs: _ood_logits())
    id_logits, id_labels = _fake_id()

    eo.calibrate_ood_thresholds(
        None, None, id_logits, id_labels,
        signal_config={}, ood_seed=3407, count_per_modulation=256,
        threshold_family="far", n_boot=50,
    )
    assert splits and all(s == "ood_validation" for s in splits)
    assert "test" not in splits
    assert "ood_final_test" not in splits


def test_metric_direction_higher_is_ood():
    id_low = np.linspace(0.0, 0.4, 100)
    ood_high = np.linspace(0.6, 1.0, 100)

    good = ranking_metrics(id_low, ood_high)
    assert good["auroc"] > 0.99
    assert good["fpr95"] < 0.01
    assert good["aupr_out"] > 0.99

    reversed_roles = ranking_metrics(ood_high, id_low)
    assert reversed_roles["auroc"] < 0.01


def test_method_ranking_deterministic():
    families = _families(shift=True)
    first = select_score_method(families)
    second = select_score_method(dict(reversed(list(families.items()))))
    assert first["recommended_score_method"] == second["recommended_score_method"]
    assert first["ranking"] == second["ranking"]
    assert first["rationale"] == second["rationale"]


def test_recommendation_picks_clearly_best_method():
    families = _families(shift=True)  # energy has the clearest separation
    recommendation = select_score_method(families)
    assert recommendation["recommended_score_method"] == "energy"
    assert recommendation["ranking"][0]["method"] == "energy"


def test_missing_metrics_forbids_selection():
    families = _families()
    del families["energy"]["ranking"]["aupr_out"]
    with pytest.raises(ValueError):
        require_complete_method_metrics(families, "energy")
    with pytest.raises(ValueError):
        select_score_method(families)


def test_freeze_uses_recommended_method_and_writes_evidence(monkeypatch, tmp_path):
    from scripts import run_threshold_freeze as rft

    families = _families(shift=True)  # energy recommended
    final_path, report_path = _freeze_inputs(tmp_path, families)
    _patch_freeze(monkeypatch, rft)

    out = tmp_path / "ood_threshold_manifest.json"
    rft.freeze_thresholds(final_path, report_path, output=str(out))

    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert manifest["score_method"] == "energy"  # recommended method chosen by default
    evidence = manifest["method_selection_evidence"]
    assert evidence["recommended_score_method"] == "energy"
    assert evidence["frozen_score_method_matches_recommended"] is True
    assert evidence["final_data_used"] is False
    assert evidence["validation_only"] is True
    assert evidence["ranking"][0]["method"] == "energy"


def test_freeze_explicit_override_records_evidence(monkeypatch, tmp_path):
    from scripts import run_threshold_freeze as rft

    families = _families(shift=True)  # energy recommended, msp is an explicit override
    final_path, report_path = _freeze_inputs(tmp_path, families)
    _patch_freeze(monkeypatch, rft)

    out = tmp_path / "ood_threshold_manifest.json"
    rft.freeze_thresholds(final_path, report_path, output=str(out), score_method="msp")

    manifest = json.loads(out.read_text(encoding="utf-8"))
    assert manifest["score_method"] == "msp"
    assert manifest["method_selection_evidence"]["frozen_score_method_matches_recommended"] is False


def test_freeze_forbids_missing_metrics(monkeypatch, tmp_path):
    from scripts import run_threshold_freeze as rft

    families = _families(shift=True)
    del families["energy"]["ranking"]  # the recommended method becomes incomplete
    final_path, report_path = _freeze_inputs(tmp_path, families)
    _patch_freeze(monkeypatch, rft)

    out = tmp_path / "ood_threshold_manifest.json"
    with pytest.raises(ValueError):
        rft.freeze_thresholds(final_path, report_path, output=str(out))
    assert not out.exists()  # nothing frozen


def test_final_data_cannot_influence_recommendation(tmp_path):
    # select_score_method takes only the calibration `families` mapping: there is no
    # parameter through which final-evaluation results could be passed.
    sig = inspect.signature(select_score_method)
    assert set(sig.parameters) == {"families", "target_operating_point"}

    families = _families(shift=True)
    before = select_score_method(families)

    # A final-results file on disk cannot change the recommendation (pure function).
    final_path = tmp_path / "final_evaluation.json"
    final_path.write_text(json.dumps({"auroc": 0.9999, "ood_detection_accuracy": 1.0}),
                          encoding="utf-8")
    assert select_score_method(families) == before
