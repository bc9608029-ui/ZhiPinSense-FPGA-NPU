"""M4: preprocessing is a pure planar transpose with no train-time statistics."""

from __future__ import annotations

import json

from training.utils import resolve_project_path


def test_preprocess_contract_no_normalization():
    data = json.loads(resolve_project_path("contracts/PREPROCESS_CONTRACT.json").read_text(encoding="utf-8"))
    assert data["normalization"] == "none (dataset pre-normalized to per-sample unit RMS)"
    assert data["finite_check"] is True
    assert data["dtype"] == "float32"


def test_input_contract_matches_shape():
    data = json.loads(resolve_project_path("contracts/rml2018_input_contract.json").read_text(encoding="utf-8"))
    assert data["input_shape"] == [1, 2, 1024]
    assert data["dtype"] == "float32"
    assert data["output_dim"] == 24
    assert data["output_kind"] == "raw_logits_no_softmax"


def test_no_train_statistics():
    data = json.loads(resolve_project_path("contracts/PREPROCESS_CONTRACT.json").read_text(encoding="utf-8"))
    assert "no mean/std" in data["train_statistics"]


def test_dataset_source_is_planar_transpose_only():
    source = resolve_project_path("datasets/radioml2018_dataset.py").read_text(encoding="utf-8")
    assert "raw.T" in source
    assert "np.ascontiguousarray" in source
