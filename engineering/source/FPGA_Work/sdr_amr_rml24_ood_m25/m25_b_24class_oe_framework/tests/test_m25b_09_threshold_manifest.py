"""Threshold-manifest tests: required keys, write-once semantics."""
import json

import pytest

from ood import m25b_threshold_manifest as m


def _record():
    return m.build_threshold_record(
        model_sha256="a" * 64, score_name="energy", split_name="ood_validation",
        id_accept_99=-5.0, id_accept_95=-4.5, far_ood=-2.0,
        id_accept_rate_at_99=0.99, far_reject_rate_at_99=0.95,
        num_id=5000, num_far_ood=5000, created_utc="2026-10-09T00:00:00Z")


def test_required_keys():
    rec = _record()
    for key in m.REQUIRED_KEYS:
        assert key in rec


def test_reject_non_validation_split():
    with pytest.raises(ValueError):
        m.build_threshold_record(
            model_sha256="a" * 64, score_name="energy", split_name="oe_aux_train",
            id_accept_99=-5.0, id_accept_95=-4.5, far_ood=-2.0,
            id_accept_rate_at_99=0.99, far_reject_rate_at_99=0.95,
            num_id=5000, num_far_ood=5000, created_utc="x")


def test_write_once_idempotent(tmp_path):
    path = str(tmp_path / "th.json")
    m.write_once(path, _record())
    m.write_once(path, _record())
    with open(path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert len(manifest) == 1


def test_write_once_refuses_different_threshold(tmp_path):
    path = str(tmp_path / "th.json")
    m.write_once(path, _record())
    other = _record()
    other["id_accept_99"] = -6.0
    with pytest.raises(RuntimeError):
        m.write_once(path, other)


def test_load_manifest_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        m.load_manifest(str(tmp_path / "nope.json"))
