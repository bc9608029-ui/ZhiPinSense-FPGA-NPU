#!/usr/bin/env python3
"""test_fix10class24_rf_dataset.py -- host tests for the dual-SDR RF dataset contract.

Pure stdlib, runs under ``python -I`` (and under pytest).  Covers the frozen
24-class contract, the source_index scheme, the capture plan, the leak-free
split, the dataset builder (accept + fail-closed rejections), and the config
YAML round-trip.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "contracts"))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
import rml24_dualsdr_rf_dataset_v1 as C  # noqa: E402
import build_fix10class24_dualsdr_rf_dataset as B  # noqa: E402


# --- helpers ----------------------------------------------------------------
def _capture(root: Path, sample_id, class_index, offset, link="dual",
             gate=C.GATE_PASSED, nbytes=8192):
    d = root / sample_id
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        "source_index": C.class_offset_to_source_index(class_index, offset),
        "link": link, "gate_status": gate, "capture_session_id": "s1",
        "payload_training_residual": 0.05,
    }
    (d / "capture_meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (d / B.SCALAR_FILENAME).write_bytes(bytes(nbytes))


def _build(root):
    with tempfile.TemporaryDirectory() as td:
        return B.build(root, Path(td) / "out", allow_provisional=True)


# --- contract ---------------------------------------------------------------
def test_label_contract_sha_matches_frozen():
    assert C.label_order_sha256() == C.FROZEN["label_contract_sha256"]
    C.assert_label_order_frozen()


def test_source_index_roundtrip():
    assert C.class_offset_to_source_index(0, 0) == 0
    assert C.class_offset_to_source_index(23, 39) == 23 * 500 + 39
    assert C.source_index_to_class(11500) == 23
    assert C.source_index_to_offset(11500) == 0
    for c in range(24):
        for o in (0, 9, 10, 39):
            si = C.class_offset_to_source_index(c, o)
            assert C.source_index_to_class(si) == c
            assert C.source_index_to_offset(si) == o


def test_deployed23_mapping():
    assert C.deployed23_index_of(17) == 17  # AM-SSB-WC -> AM-SSB
    assert C.deployed23_index_of(18) == 17  # AM-SSB-SC -> AM-SSB
    assert C.deployed23_label_of(17) == "AM-SSB"
    assert C.deployed23_label_of(18) == "AM-SSB"
    assert C.deployed23_index_of(23) == 22  # OQPSK
    assert C.deployed23_label_of(23) == "OQPSK"


def test_plan_has_960_rows():
    rows = list(C.capture_plan_rows())
    assert len(rows) == 960
    assert sum(1 for r in rows if r["phase"] == "pilot") == 240
    assert sum(1 for r in rows if r["phase"] == "formal") == 720


def test_plan_source_indices_unique():
    rows = list(C.capture_plan_rows())
    assert len({r["source_index"] for r in rows}) == len(rows)


def test_split_is_leakfree_and_sized():
    C.assert_split_is_leakfree()
    assert len(C.FORMAL_TRAIN_OFFSETS) == 18
    assert len(C.FORMAL_VAL_OFFSETS) == 6
    assert len(C.FORMAL_TEST_OFFSETS) == 6
    assert C.split_role_of("formal", 10) == "train"
    assert C.split_role_of("formal", 28) == "val"
    assert C.split_role_of("formal", 34) == "test"
    assert C.split_role_of("pilot", 5) == "pilot"


def test_rf_config_frozen():
    assert C.RF_CONFIG["center_freq_hz"] == 2400000000
    assert C.RF_CONFIG["sample_rate_hz"] == 2560000
    assert C.RF_CONFIG["rx_gain"] == 35
    assert C.RF_CONFIG["tx_atten_db"] == -40
    assert C.RF_CONFIG["tx_target_rms"] == 2048
    assert C.RF_CONFIG["rf_path"] == "direct-cable"


# --- builder ----------------------------------------------------------------
def test_builder_accepts_valid_capture():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "cap"
        _capture(root, "c00_000", 0, 0, gate=C.GATE_DIAGNOSTIC_PROVISIONAL)  # pilot
        _capture(root, "c00_010", 0, 10)   # train
        _capture(root, "c00_011", 0, 11, gate=C.GATE_REJECTED)  # rejected
        _capture(root, "c00_028", 0, 28)   # val
        _capture(root, "c00_034", 0, 34)   # test
        _capture(root, "c01_010", 1, 10)   # train (class 1)
        report = _build(root)
        assert report["accepted"] == 5
        assert report["rejected"] == 1
        assert report["split_counts"] == {"train": 2, "val": 1, "test": 1, "pilot": 1}
        assert report["contract_sha256"] == C.dataset_contract_sha256()


def test_builder_rejects_duplicate_source_index():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "cap"
        _capture(root, "a", 0, 10)
        _capture(root, "b", 0, 10)  # duplicate
        try:
            _build(root)
            assert False, "expected BuildError"
        except B.BuildError as e:
            assert "duplicate source_index" in str(e)


def test_builder_rejects_unplanned_source_index():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "cap"
        _capture(root, "a", 0, 40)  # offset 40 is outside the plan
        try:
            _build(root)
            assert False, "expected BuildError"
        except B.BuildError as e:
            assert "not a planned slot" in str(e)


def test_builder_rejects_provisional_in_train():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "cap"
        _capture(root, "a", 0, 10, gate=C.GATE_DIAGNOSTIC_PROVISIONAL)  # train slot
        try:
            _build(root)
            assert False, "expected BuildError"
        except B.BuildError as e:
            assert "provisional" in str(e).lower() or "train" in str(e).lower()


def test_builder_rejects_bad_model_input_size():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "cap"
        _capture(root, "a", 0, 10, nbytes=8000)  # wrong size
        try:
            _build(root)
            assert False, "expected BuildError"
        except B.BuildError as e:
            assert "8192" in str(e)


def test_builder_rejects_missing_meta_field():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "cap"
        d = root / "a"
        d.mkdir(parents=True)
        (d / "capture_meta.json").write_text('{"source_index": 5000}', encoding="utf-8")
        (d / B.SCALAR_FILENAME).write_bytes(bytes(8192))
        try:
            _build(root)
            assert False, "expected BuildError"
        except B.BuildError as e:
            assert "missing required field" in str(e)


# --- config yaml ------------------------------------------------------------
def test_yaml_roundtrip_matches_spec():
    text = C.yaml_dump_simple(C.PILOT_TRAINING_SPEC)
    assert C.yaml_load_simple(text) == C.PILOT_TRAINING_SPEC


def test_config_yaml_file_matches_spec():
    yaml_path = os.path.join(_ROOT, "training", "configs",
                             "fix10class24_rf_adapt_pilot.yaml")
    assert os.path.isfile(yaml_path), f"missing {yaml_path}"
    text = Path(yaml_path).read_text(encoding="utf-8")
    assert C.yaml_load_simple(text) == C.PILOT_TRAINING_SPEC


def _run_all():
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    passed = failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS  {name}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAIL  {name}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed / {failed} failed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if _run_all() else 0)
