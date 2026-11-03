"""M3: the frozen train/validation/test split must be a leak-free partition."""

from __future__ import annotations

import json

import numpy as np
import pytest

from training.utils import resolve_project_path

INDEX_PATH = "data/radioml2018/rml24_split_indices.npz"
CONTRACT_PATH = "contracts/rml2018_data_contract.json"
TOTAL_SAMPLES = 2555904


def _load_index():
    path = resolve_project_path(INDEX_PATH)
    if not path.is_file():
        pytest.skip("split index not generated yet; run run_data_audit.sh first")
    return np.load(path, allow_pickle=False)


def test_split_counts_match_contract():
    contract = json.loads(resolve_project_path(CONTRACT_PATH).read_text(encoding="utf-8"))
    indices = _load_index()
    for split, expected in contract["split_counts"].items():
        assert len(indices[f"{split}_indices"]) == int(expected)


def test_no_overlap_and_full_partition():
    indices = _load_index()
    seen = np.zeros(TOTAL_SAMPLES, dtype=bool)
    for split in ("train", "validation", "test"):
        idx = indices[f"{split}_indices"]
        assert not seen[idx].any(), f"{split} overlaps an earlier split"
        seen[idx] = True
    assert int(seen.sum()) == TOTAL_SAMPLES


def test_indices_in_range_and_unique():
    indices = _load_index()
    for split in ("train", "validation", "test"):
        idx = indices[f"{split}_indices"]
        assert idx.min() >= 0 and idx.max() < TOTAL_SAMPLES
        assert len(np.unique(idx)) == len(idx)


def test_labels_and_snrs_valid():
    indices = _load_index()
    snr_set = set(range(-20, 31, 2))
    for split in ("train", "validation", "test"):
        idx = indices[f"{split}_indices"]
        labels = indices[f"{split}_labels"]
        snrs = indices[f"{split}_snrs"]
        assert len(labels) == len(idx) == len(snrs)
        assert labels.min() >= 0 and labels.max() < 24
        assert set(np.unique(snrs).astype(int).tolist()) <= snr_set
