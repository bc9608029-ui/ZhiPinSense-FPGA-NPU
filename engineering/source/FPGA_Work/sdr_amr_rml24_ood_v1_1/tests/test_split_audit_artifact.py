"""V1.1 reliability — machine-local data/split contract artifacts.

``run_data_audit.sh`` must additionally land ``artifacts/data_contract.json`` and
``artifacts/split_audit.json`` (per-stratum counts + leakage + worker invariance).
These tests exercise the two emission helpers on a synthetic report, so they run
offline without the 21 GiB HDF5.
"""

from __future__ import annotations

import json

from data_tools.audit_rml2018 import _write_data_contract_artifact, _write_split_audit


def _report() -> dict:
    strata = {f"class{i}@{-20 + 2 * j}": 4096 for i in range(24) for j in range(26)}
    return {
        "status": "pass",
        "dataset": "RadioML2018.01A",
        "hdf5_path": "/data/GOLD_XYZ_OSC.0001_1024.hdf5",
        "size_bytes": 21449148312,
        "mtime_ns": 1,
        "sha256": "a" * 64,
        "class_names": [f"class{i}" for i in range(24)],
        "sample_shape": [1024, 2],
        "samples": 2555904,
        "split_seed": 20261003,
        "split_ratios": [0.6, 0.2, 0.2],
        "split_counts": {"train": 1533168, "validation": 511056, "test": 511680},
        "strata_counts": strata,
        "index_path": "/data/rml24_split_indices.npz",
        "index_sha256": "b" * 64,
        "overlap_counts": {"train_validation": 0, "train_test": 0, "validation_test": 0},
        "synthetic_fallback": False,
    }


def test_split_audit_has_strata_counts_and_leakage(tmp_path):
    path = _write_split_audit(_report(), tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["split_seed"] == 20261003
    assert data["split_counts"] == {"train": 1533168, "validation": 511056, "test": 511680}
    assert data["overlap_counts"] == {"train_validation": 0, "train_test": 0, "validation_test": 0}
    # per-(class,SNR) layer counts: 24 x 26 = 624 strata, each 4096.
    assert len(data["strata_counts"]) == 624
    assert all(count == 4096 for count in data["strata_counts"].values())
    assert "worker_invariance" in data
    assert "split_seed" in data["worker_invariance"]


def test_split_audit_counts_are_consistent(tmp_path):
    data = json.loads(_write_split_audit(_report(), tmp_path).read_text(encoding="utf-8"))
    assert sum(data["split_counts"].values()) == 2555904
    # The split is per-(class,SNR) stratum: 624 strata x 4096 samples, with the
    # 0.6/0.2/0.2 ratios floored per stratum (2457/819/820), then re-summed.
    assert data["split_counts"]["train"] == 624 * int(4096 * 0.6)
    assert data["split_counts"]["validation"] == 624 * int(4096 * 0.2)


def test_data_contract_artifact_is_machine_local_superset(tmp_path):
    path = _write_data_contract_artifact(_report(), tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["sha256"] == "a" * 64
    assert data["index_sha256"] == "b" * 64
    assert data["num_classes"] == 24
    # machine-local fields the portable contract deliberately excludes
    assert data["hdf5_path"] == "/data/GOLD_XYZ_OSC.0001_1024.hdf5"
    assert data["mtime_ns"] == 1
    assert data["index_path"] == "/data/rml24_split_indices.npz"
    assert data["overlap_counts"]["train_validation"] == 0
