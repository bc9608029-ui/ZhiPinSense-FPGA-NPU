"""Mirrors tests/test_mock.cpp against the Python generator, and validates the
committed mock_data/*.jsonl replay files (when present)."""

from __future__ import annotations

import json
import os

from generate_mock_data import (
    CLASS_NAMES,
    CONTRACT_VERSION,
    DEFAULT_FRAMES,
    MODEL_ID,
    SCENARIOS,
    Mock,
    generate,
)
from frame_validator_mirror import validate_frame

DEFAULT_SEED = 0x20261002


def drain(scenario, cap=1000):
    m = Mock(scenario)
    return [m.make_frame() for _ in range(cap)]


def test_scenario_names_cover_ten():
    assert len(SCENARIOS) == 10


def test_all_scenarios_valid_ten_class():
    for sc in SCENARIOS:
        for f in drain(sc):
            assert f["contract_version"] == CONTRACT_VERSION
            assert f["model_id"] == MODEL_ID
            assert len(f["class_names"]) == 10
            assert len(f["scores"]) == 10
            assert f["source"] == "MOCK"
            assert validate_frame(f) == "", "invalid frame in %s" % sc


def test_normal_monotonic_and_class():
    frames = drain("normal")
    for i, f in enumerate(frames):
        assert f["frame_id"] == i
    assert frames[0]["predicted_index"] == 7
    assert frames[0]["predicted_class"] == "16QAM"


def test_reorder_frame_id():
    frames = drain("reorder")
    saw = False
    for i, f in enumerate(frames):
        if i >= 2 and i % 40 == 20:
            assert f["frame_id"] == i - 2
            assert f["counters"]["reorder"] == 1
            saw = True
        else:
            assert f["counters"]["reorder"] == 0
    assert saw


def test_drop_overflow_counters():
    frames = drain("drop_overflow")
    saw = False
    for i, f in enumerate(frames):
        if i > 0 and i % 50 == 0:
            assert f["counters"]["dropped"] == 3
            assert f["counters"]["overflow"] == 1
            saw = True
    assert saw


def test_stale_frame_count():
    text = generate("stale", DEFAULT_FRAMES["stale"], DEFAULT_SEED, 15.0)
    lines = [l for l in text.splitlines() if l]
    assert len(lines) == 30
    for line in lines:
        f = json.loads(line)
        assert f["sdr_status"] == "ok" and f["fpga_status"] == "ok" and f["npu_status"] == "ok"


def test_sdr_disconnect_last_disconnected():
    text = generate("sdr_disconnect", DEFAULT_FRAMES["sdr_disconnect"], DEFAULT_SEED, 15.0)
    lines = [l for l in text.splitlines() if l]
    assert len(lines) == 31
    assert json.loads(lines[-1])["sdr_status"] == "disconnected"


def test_determinism():
    a = drain("recovery", cap=120)
    b = drain("recovery", cap=120)
    assert len(a) == len(b)
    for x, y in zip(a, b):
        for k in x:
            if k == "timestamp_ns":
                continue
            assert x[k] == y[k]


def test_generated_files_validate():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(root, "mock_data")
    if not os.path.isdir(data_dir):
        return  # not generated yet; generation is a separate build step
    for sc in SCENARIOS:
        path = os.path.join(data_dir, sc + ".jsonl")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                f = json.loads(line)
                assert validate_frame(f) == "", "invalid frame in %s" % sc
