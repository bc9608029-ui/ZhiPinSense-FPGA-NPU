"""V1.1 reliability — frozen OOD threshold manifest (write-once, fail-closed read)."""

from __future__ import annotations

import json

import pytest

from ood.threshold_manifest import (
    build_threshold_manifest,
    read_threshold_manifest,
    write_threshold_manifest,
)


def _thresholds():
    return {
        "conservative": {"threshold": 0.1, "id_frr": 0.04, "ood_far": 0.8},
        "balanced": {"threshold": 0.5, "id_frr": 0.02, "ood_far": 0.1},
        "strict": {"threshold": 0.9, "id_frr": 0.01, "ood_far": 0.03},
    }


def _manifest(**overrides):
    base = dict(
        model_sha256="a" * 64,
        checkpoint_sha256="b" * 64,
        score_method="energy",
        thresholds=_thresholds(),
        calibration_dataset_sha256="c" * 64,
        calibration_split_sha256="d" * 64,
        target_operating_point="balanced",
        calibration_samples={"id": 511056, "ood": 200000},
        creation_seed=2026,
        temperature=1.0,
    )
    base.update(overrides)
    return build_threshold_manifest(**base)


def test_build_write_read_round_trip(tmp_path):
    manifest = _manifest()
    path = write_threshold_manifest(manifest, tmp_path / "ood_threshold_manifest.json")
    loaded = read_threshold_manifest(path)
    assert loaded["score_method"] == "energy"
    assert loaded["temperature"] == 1.0
    assert tuple(loaded["thresholds"]) == ("conservative", "balanced", "strict")
    assert loaded["thresholds"]["balanced"]["threshold"] == 0.5
    assert loaded["calibration_samples"] == {"id": 511056, "ood": 200000}
    assert loaded["creation_seed"] == 2026


def test_write_once_refuses_overwrite(tmp_path):
    path = tmp_path / "ood_threshold_manifest.json"
    write_threshold_manifest(_manifest(), path)
    with pytest.raises(FileExistsError):
        write_threshold_manifest(_manifest(), path)
    # Explicit escape hatch still works.
    write_threshold_manifest(_manifest(), path, overwrite=True)


def test_read_missing_file_fails_closed(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_threshold_manifest(tmp_path / "nope.json")


def test_read_malformed_json_fails_closed(tmp_path):
    path = tmp_path / "ood_threshold_manifest.json"
    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ValueError):
        read_threshold_manifest(path)


def test_build_rejects_bad_score_method():
    with pytest.raises(ValueError):
        _manifest(score_method="mahalanobis")


def test_build_rejects_bad_target_operating_point():
    with pytest.raises(ValueError):
        _manifest(target_operating_point="aggressive")


def test_build_rejects_non_hex_sha():
    with pytest.raises(ValueError):
        _manifest(model_sha256="zz" * 32)


def test_build_rejects_non_finite_threshold():
    thresholds = _thresholds()
    thresholds["balanced"]["threshold"] = float("nan")
    with pytest.raises(ValueError):
        _manifest(thresholds=thresholds)


def test_build_rejects_non_positive_temperature():
    with pytest.raises(ValueError):
        _manifest(temperature=0.0)


def test_build_rejects_missing_calibration_samples():
    with pytest.raises(ValueError):
        _manifest(calibration_samples={"id": 10})


def test_manifest_is_json_serializable():
    assert json.dumps(_manifest(), sort_keys=True)
