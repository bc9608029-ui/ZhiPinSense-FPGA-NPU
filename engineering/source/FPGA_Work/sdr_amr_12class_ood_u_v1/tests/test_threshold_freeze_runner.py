"""V1.1 reliability — Task I wiring: freeze the OOD threshold manifest.

``scripts.run_threshold_freeze`` promotes the thresholds locked in the OOD
baselines report into a write-once manifest.  These tests exercise the runner on
synthetic inputs (offline, no HDF5 / model).
"""

from __future__ import annotations

import json

import pytest

from scripts.run_threshold_freeze import (
    calibration_split_sha256,
    freeze_thresholds,
)
from ood.threshold_manifest import read_threshold_manifest


def _thresholds():
    return {
        "conservative": {"threshold": 0.1, "id_frr": 0.04, "ood_far": 0.8},
        "balanced": {"threshold": 0.5, "id_frr": 0.02, "ood_far": 0.1},
        "strict": {"threshold": 0.9, "id_frr": 0.01, "ood_far": 0.03},
    }


def _ood_report():
    return {"rml24": {
        "families": {"energy": {"thresholds": _thresholds()}},
        "calibrated_temperature": 1.05,
        "id_samples": 511680,
        "threshold_family": "far",
    }}


def _final_manifest():
    return {"checkpoint_sha256": "b" * 64, "dataset_sha256": "c" * 64}


def test_calibration_split_sha256_is_deterministic():
    assert calibration_split_sha256("far", 3407, 256) == calibration_split_sha256("far", 3407, 256)
    assert calibration_split_sha256("far", 3407, 256) != calibration_split_sha256("near_24", 3407, 256)
    assert len(calibration_split_sha256("far", 3407, 256)) == 64


def test_freeze_thresholds_writes_valid_manifest(tmp_path):
    final = tmp_path / "final.json"
    final.write_text(json.dumps(_final_manifest()), encoding="utf-8")
    ood = tmp_path / "ood.json"
    ood.write_text(json.dumps(_ood_report()), encoding="utf-8")
    out = tmp_path / "ood_threshold_manifest.json"

    result = freeze_thresholds(final, ood, output=out, ood_seed=3407, count_per_modulation=256)

    manifest = read_threshold_manifest(out)
    assert manifest["score_method"] == "energy"
    assert manifest["checkpoint_sha256"] == "b" * 64
    assert manifest["calibration_dataset_sha256"] == "c" * 64
    # far family has 5 modulations; 5 * 256 = 1280 calibration OOD samples.
    assert manifest["calibration_samples"] == {"id": 511680, "ood": 1280}
    assert manifest["temperature"] == 1.05
    assert tuple(manifest["thresholds"]) == ("conservative", "balanced", "strict")
    assert result["manifest"] == str(out)


def test_freeze_thresholds_refuses_unknown_score_method(tmp_path):
    final = tmp_path / "final.json"
    final.write_text(json.dumps(_final_manifest()), encoding="utf-8")
    ood = tmp_path / "ood.json"
    ood.write_text(json.dumps(_ood_report()), encoding="utf-8")
    with pytest.raises(KeyError):
        freeze_thresholds(final, ood, output=tmp_path / "m.json",
                          ood_seed=3407, score_method="mahalanobis")
