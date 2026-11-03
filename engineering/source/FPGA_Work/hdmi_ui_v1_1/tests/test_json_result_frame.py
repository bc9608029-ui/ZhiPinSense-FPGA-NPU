"""Mirrors tests/test_json_result_frame.cpp: V1.1 and legacy parse shapes,
malformed input, missing version, and a to_json round-trip — via the Python
twin of src/json_result_frame.cpp."""

from __future__ import annotations

import json

from frame_validator_mirror import (
    LEGACY_CLASS_NAMES,
    parse_result_frame,
)

V11 = {
    "contract_version": 2, "model_id": "m",
    "frame_id": 5, "timestamp_ns": 1, "source": "MOCK",
    "class_names": ["AM-DSB", "WBFM", "2FSK", "GFSK", "BPSK",
                    "QPSK", "8PSK", "16QAM", "64QAM", "OFDM"],
    "scores": [0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01, 0.9, 0.02, 0.01],
    "predicted_index": 7, "predicted_class": "16QAM", "confidence": 0.9,
    "snr_db": 18.0, "center_frequency_hz": 2400000000.0, "sample_rate_hz": 128000.0,
    "latency_us": {"sdr_capture": 1, "resample_frame": 1, "plddr_transfer": 1,
                   "fpga_process": 1, "npu_infer": 1, "end_to_end": 5},
    "fps": 15.0,
    "counters": {"dropped": 0, "overflow": 0, "duplicate": 0,
                 "reorder": 0, "timeout": 0, "error": 0},
    "sdr_status": "ok", "fpga_status": "ok", "npu_status": "ok",
}

LEGACY = {
    "schema_version": 1,
    "frame_id": 3, "timestamp_ns": 1, "source": "FILE",
    "class_id": 3, "class_name": "16QAM", "confidence": 0.8,
    "probabilities": [0.01, 0.01, 0.01, 0.8, 0.1, 0.03, 0.02, 0.02],
    "snr_db": 15.0, "center_frequency_hz": 2400000000.0, "sample_rate_hz": 128000.0,
    "latency_us": {"sdr_capture": 1, "resample_frame": 1, "plddr_transfer": 1,
                   "fpga_process": 1, "npu_infer": 1, "end_to_end": 5},
    "fps": 15.0,
    "counters": {"dropped": 0, "overflow": 0, "duplicate": 0,
                 "reorder": 0, "timeout": 0, "error": 0},
    "sdr_status": "ok", "fpga_status": "ok", "npu_status": "ok",
}


def test_parse_v1_1():
    f, err = parse_result_frame(json.dumps(V11))
    assert err == ""
    assert f["contract_version"] == 2 and f["model_id"] == "m"
    assert len(f["class_names"]) == 10 and len(f["scores"]) == 10
    assert f["predicted_index"] == 7 and f["predicted_class"] == "16QAM"
    assert f["source"] == "MOCK" and f["frame_id"] == 5


def test_parse_legacy():
    f, err = parse_result_frame(json.dumps(LEGACY))
    assert err == ""
    assert f["contract_version"] == 1 and f["model_id"] == ""
    assert f["predicted_index"] == 3 and f["predicted_class"] == "16QAM"
    assert f["class_names"] == LEGACY_CLASS_NAMES
    assert len(f["scores"]) == 8
    assert f["source"] == "FILE"


def test_malformed_rejected():
    f, err = parse_result_frame("{not json")
    assert f is None and err.startswith("json parse:")


def test_non_object_rejected():
    f, err = parse_result_frame("[1, 2, 3]")
    assert f is None and err == "json: root is not an object"


def test_missing_version_rejected():
    f, err = parse_result_frame(json.dumps({"frame_id": 1}))
    assert f is None and "missing contract_version" in err


def test_round_trip():
    f, _ = parse_result_frame(json.dumps(V11))
    line = json.dumps(f)
    rt, err = parse_result_frame(line)
    assert err == ""
    assert rt["frame_id"] == f["frame_id"]
    assert rt["predicted_class"] == f["predicted_class"]
    assert rt["confidence"] == f["confidence"]
    assert rt["model_id"] == f["model_id"]
