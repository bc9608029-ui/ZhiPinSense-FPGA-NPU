"""Validate the generated mock_data against the contract.

Covers, per scenario and per frame:

* JSON-Schema conformance (contracts/result_frame.schema.json);
* the C++ ``validate()`` mirror (tests/frame_validator_mirror.py);
* structural invariants (class order, probability sum, confidence, counters,
  spectrum length, latency decomposition);
* deterministic regeneration (regenerating with the same seed reproduces the
  committed bytes exactly);
* scenario-specific semantics (fault injection, drops, recovery, disconnect).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os

import jsonschema

from frame_validator_mirror import CLASS_NAMES, validate_frame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_PATH = os.path.join(ROOT, "contracts", "result_frame.schema.json")
MOCK_DIR = os.path.join(ROOT, "mock_data")

SCENARIOS = [
    "normal",
    "modulation_switch",
    "low_confidence",
    "sdr_disconnect",
    "fpga_error",
    "npu_timeout",
    "drop_overflow",
    "recovery",
]

with open(SCHEMA_PATH, encoding="utf-8") as fh:
    SCHEMA = json.load(fh)


def _load_gen():
    spec = importlib.util.spec_from_file_location(
        "generate_mock_data",
        os.path.join(ROOT, "scripts", "generate_mock_data.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GEN = _load_gen()


def _frames(scenario):
    path = os.path.join(MOCK_DIR, scenario + ".jsonl")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _all_frames():
    for sc in SCENARIOS:
        for f in _frames(sc):
            yield sc, f


def test_every_frame_matches_schema():
    for sc, frame in _all_frames():
        jsonschema.validate(frame, SCHEMA)


def test_every_frame_passes_contract_validate():
    for sc, frame in _all_frames():
        reason = validate_frame(frame)
        assert reason == "", (sc, frame.get("frame_id"), reason)


def test_structural_invariants():
    for sc, f in _all_frames():
        assert f["class_name"] == CLASS_NAMES[f["class_id"]], sc
        assert len(f["probabilities"]) == 8, sc
        assert abs(sum(f["probabilities"]) - 1.0) < 1e-6, sc
        assert f["confidence"] == f["probabilities"][f["class_id"]], sc
        for k in ("dropped", "overflow", "duplicate", "reorder", "timeout", "error"):
            assert isinstance(f["counters"][k], int), (sc, k)
            assert f["counters"][k] >= 0, (sc, k)
        assert len(f["spectrum_bins"]) == 128, sc
        lat = f["latency_us"]
        stages = (lat["sdr_capture"] + lat["resample_frame"] + lat["plddr_transfer"]
                  + lat["fpga_process"] + lat["npu_infer"])
        assert abs(lat["end_to_end"] - stages) < 1e-6, sc
        assert f["source"] == "MOCK", sc


def test_manifest_matches_files():
    with open(os.path.join(MOCK_DIR, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert manifest["class_order"] == CLASS_NAMES
    by_sc = {e["scenario"]: e for e in manifest["scenarios"]}
    assert set(by_sc) == set(SCENARIOS)
    for sc in SCENARIOS:
        with open(os.path.join(MOCK_DIR, sc + ".jsonl"), "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        assert by_sc[sc]["sha256"] == digest, sc
        assert by_sc[sc]["frames"] == len(_frames(sc)), sc


def test_deterministic_regeneration_matches_committed():
    for sc in SCENARIOS:
        text = GEN.generate(sc, GEN.DEFAULT_FRAMES[sc], GEN.DEFAULT_SEED, GEN.DEFAULT_FPS)
        with open(os.path.join(MOCK_DIR, sc + ".jsonl"), encoding="utf-8") as fh:
            assert text == fh.read(), sc


def test_scenario_normal():
    frames = _frames("normal")
    assert len(frames) == 200
    assert all(f["class_id"] == 3 for f in frames)
    assert all(f["sdr_status"] == f["fpga_status"] == f["npu_status"] == "ok" for f in frames)
    assert all(f["confidence"] > 0.5 for f in frames)


def test_scenario_modulation_switch():
    frames = _frames("modulation_switch")
    seq = [0, 3, 4, 6]
    for i, f in enumerate(frames):
        assert f["class_id"] == seq[(i // 40) % 4], i


def test_scenario_low_confidence():
    frames = _frames("low_confidence")
    assert all(f["class_id"] == 2 for f in frames)
    assert all(f["confidence"] < 0.5 for f in frames)


def test_scenario_sdr_disconnect():
    frames = _frames("sdr_disconnect")
    assert len(frames) == 31
    assert all(f["sdr_status"] == "ok" for f in frames[:30])
    assert frames[30]["sdr_status"] == "disconnected"


def test_scenario_fpga_error():
    frames = _frames("fpga_error")
    assert all(f["fpga_status"] == "ok" for f in frames[:30])
    for f in frames[30:]:
        assert f["fpga_status"] == "error"
        assert f["counters"]["error"] == 1


def test_scenario_npu_timeout():
    frames = _frames("npu_timeout")
    assert all(f["npu_status"] == "ok" for f in frames[:30])
    for f in frames[30:]:
        assert f["npu_status"] == "error"
        assert f["counters"]["timeout"] == 1


def test_scenario_drop_overflow():
    frames = _frames("drop_overflow")
    drop_at = {50, 100, 150}

    def offset(i):
        return 3 * sum(1 for d in drop_at if i >= d)

    for i, f in enumerate(frames):
        assert f["frame_id"] == i + offset(i), i
        if i in drop_at:
            assert f["counters"]["dropped"] == 3, i
            assert f["counters"]["overflow"] == 1, i
        else:
            assert f["counters"]["dropped"] == 0, i


def test_scenario_recovery():
    frames = _frames("recovery")
    assert all(f["fpga_status"] == "ok" for f in frames[:30])
    for f in frames[30:60]:
        assert f["fpga_status"] == "error"
        assert f["counters"]["error"] == 1
    assert all(f["fpga_status"] == "ok" for f in frames[60:])
