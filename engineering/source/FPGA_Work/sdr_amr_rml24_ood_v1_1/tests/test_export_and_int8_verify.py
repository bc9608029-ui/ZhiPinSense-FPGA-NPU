"""V1.1 reliability — Task K: ONNX / fake-INT8 verification helpers.

Offline-testable pure-logic pieces: the confusion-matrix / per-class-recall /
near-QAM-PSK helpers used by ``fake_int8_report_rml24``, and the export
argmax / OOD-score parity, raw-logits and manifest fail-closed checks in
``scripts.export_rml24_onnx``.  The full ONNX export is exercised on AutoDL by
``cuda_preflight.check_onnx_export_parity`` and by ``run_export.sh``.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
import torch

from evaluation.evaluate_rml24 import (
    _confusion_matrix,
    _near_qam_psk_confusion,
    _per_class_recall,
)
from scripts.export_rml24_onnx import (
    _argmax_parity,
    _assert_no_softmax,
    _ood_score_parity,
    _sha256_file,
    export_rml24,
)


def test_confusion_matrix_row_is_target():
    cm = _confusion_matrix(np.array([0, 1, 0]), np.array([0, 0, 1]), 3)
    assert cm.shape == (3, 3)
    assert cm[0, 0] == 1 and cm[0, 1] == 1  # target 0 predicted 0 and 1
    assert cm[1, 0] == 1  # target 1 predicted 0


def test_per_class_recall_matches_accuracy():
    cm = _confusion_matrix(np.array([0, 0, 1, 2, 2, 2]),
                           np.array([0, 1, 1, 2, 2, 0]), 3)
    assert _per_class_recall(cm) == pytest.approx([0.5, 1.0, 2 / 3])


def test_per_class_recall_empty_row_is_zero():
    cm = np.zeros((3, 3), dtype=np.int64)
    cm[0, 0] = 1
    assert _per_class_recall(cm)[1] == 0.0


def test_near_qam_psk_confusion_restricts_block():
    cm = _confusion_matrix(np.arange(24), np.arange(24), 24)
    block = _near_qam_psk_confusion(cm)
    assert block["indices"] == [3, 4, 5, 6, 7, 12, 13, 14, 15, 16]
    assert block["class_names"][0] == "BPSK" and block["class_names"][-1] == "256QAM"
    assert len(block["matrix"]) == 10 and all(len(row) == 10 for row in block["matrix"])


def test_argmax_parity_detects_mismatch():
    a = np.array([[0.1, 0.9], [0.8, 0.2]])
    assert _argmax_parity(a, a)["match"] is True
    b = np.array([[0.9, 0.1], [0.8, 0.2]])
    res = _argmax_parity(a, b)
    assert res["match"] is False and res["mismatch_count"] == 1


def test_ood_score_parity_self_is_ok():
    logits = np.random.default_rng(0).normal(size=(32, 24)).astype(np.float32)
    parity = _ood_score_parity(logits, logits)
    assert parity["energy"]["status"] == "ok"
    assert parity["msp"]["status"] == "ok"
    assert parity["energy"]["max_abs_diff"] == 0.0


def test_assert_no_softmax_rejects_softmax():
    _assert_no_softmax(torch.nn.Identity())
    with pytest.raises(RuntimeError):
        _assert_no_softmax(torch.nn.Softmax(dim=1))


def test_sha256_file(tmp_path):
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello")
    assert _sha256_file(p) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def _write_manifest(tmp_path, **overrides):
    manifest = {"class_count": 24, "model_name": "RML2018_24_BENCHMARK",
                "checkpoint_path": str(tmp_path / "best.pt"),
                "checkpoint_sha256": "0" * 64, "label_contract_sha256": "a" * 64}
    manifest.update(overrides)
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def _cfg(tmp_path):
    return {"model": {}, "signal": {}, "output_root": str(tmp_path), "seed": 0}


def test_export_manifest_wrong_sha_fails_closed(tmp_path):
    (tmp_path / "best.pt").write_bytes(b"not-a-real-checkpoint")
    manifest_path = _write_manifest(tmp_path)
    with pytest.raises(RuntimeError, match="checkpoint SHA"):
        export_rml24(_cfg(tmp_path), tmp_path / "best.pt", manifest_path=manifest_path)


def test_export_manifest_bad_class_count_fails_closed(tmp_path):
    manifest_path = _write_manifest(tmp_path, class_count=12)
    with pytest.raises(RuntimeError, match="class_count"):
        export_rml24(_cfg(tmp_path), tmp_path / "best.pt", manifest_path=manifest_path)


def test_export_manifest_missing_model_name_fails_closed(tmp_path):
    manifest_path = _write_manifest(tmp_path, model_name="")
    with pytest.raises(RuntimeError, match="model_name"):
        export_rml24(_cfg(tmp_path), tmp_path / "best.pt", manifest_path=manifest_path)
