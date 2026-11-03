"""M20 test categories 8-9: model SHA binding + manifest write-once.

The frozen model identity (checkpoint / ONNX / NPU JSON / NPU raw) must match
the contract byte-for-byte, and the OOD-U manifest must be write-once and
fail-closed on any contract violation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ood_u import contract
from ood_u.manifest import build_ood_u_manifest, read_ood_u_manifest, write_ood_u_manifest
from ood_u.model import _load_checkpoint_dict, sha256_file

_PROJECT = Path(__file__).resolve().parents[1]


def test_model_sha_binding_files_match_contract():
    # Category 8: every authoritative artifact SHA matches the frozen contract.
    assert sha256_file(_PROJECT / "model_12class/seed2026_best.pt") == contract.CHECKPOINT_SHA256
    assert sha256_file(_PROJECT / "model_12class/ad_amr_v1_1_opset17.onnx") == contract.ONNX_SHA256
    assert sha256_file(_PROJECT / "model_12class/model_12class.json") == contract.NPU_JSON_SHA256
    assert sha256_file(_PROJECT / "model_12class/model_12class.raw") == contract.MODEL_SHA256


def test_model_sha_binding_loader_fails_on_mismatch(tmp_path):
    # A wrong-SHA checkpoint must fail closed before any torch.load.
    fake = tmp_path / "fake.pt"
    fake.write_bytes(b"not the real checkpoint")
    with pytest.raises(RuntimeError):
        _load_checkpoint_dict(fake)


def test_manifest_write_once(tmp_path):
    # Category 9: the manifest is write-once; a second write must raise.
    manifest = build_ood_u_manifest(
        score_method="logit_margin", temperature=1.0, threshold=-0.153,
        working_points={
            "id_accept_95": {"threshold": -0.5},
            "id_accept_99": {"threshold": -0.153},
            "far_ood_target": {"threshold": -15.0},
        },
        target_operating_point="id_accept_99",
        calibration_dataset_sha256="a" * 64,
        calibration_split_sha256="b" * 64,
        sample_count={"id": 720, "ood": 1080},
        creation_seed=contract.OOD_SEED,
    )
    path = tmp_path / "manifest.json"
    write_ood_u_manifest(manifest, path)
    assert read_ood_u_manifest(path)["score_method"] == "logit_margin"
    with pytest.raises(FileExistsError):
        write_ood_u_manifest(manifest, path)


def test_manifest_rejects_wrong_model_sha(tmp_path):
    # A manifest bound to the wrong NPU model must be rejected on read.
    manifest = build_ood_u_manifest(
        score_method="msp", temperature=1.0, threshold=0.0,
        working_points={
            "id_accept_95": {"threshold": -0.5},
            "id_accept_99": {"threshold": -0.153},
            "far_ood_target": {"threshold": -15.0},
        },
        target_operating_point="id_accept_99",
        calibration_dataset_sha256="a" * 64,
        calibration_split_sha256="b" * 64,
        sample_count={"id": 1, "ood": 1},
        creation_seed=contract.OOD_SEED,
    )
    manifest["model_sha256"] = "0" * 64
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        read_ood_u_manifest(path)
