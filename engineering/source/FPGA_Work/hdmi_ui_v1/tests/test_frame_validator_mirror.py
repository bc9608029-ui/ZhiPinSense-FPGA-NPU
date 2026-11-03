"""Tests for the Python mirror of the Qt-free consumer-side integrity layer.

These exercise the exact same sequence/stale/validate semantics the C++ in
src/frame_validator.hpp and contracts/result_frame.hpp implements, so the two
languages are kept in lock-step from the host.
"""

from __future__ import annotations

import math

from frame_validator_mirror import (
    CLASS_NAMES,
    LATENCY_KEYS,
    FrameSequenceMonitor,
    StaleDetector,
    class_id_of,
    is_stale,
    validate_frame,
)


def make_valid_frame(**overrides):
    frame = {
        "schema_version": 1,
        "frame_id": 0,
        "timestamp_ns": 0,
        "source": "MOCK",
        "class_id": 3,
        "class_name": "16QAM",
        "confidence": 0.9,
        "probabilities": [0.0] * 8,
        "snr_db": 18.0,
        "center_frequency_hz": 2.4e9,
        "sample_rate_hz": 128000.0,
        "latency_us": {k: 1.0 for k in LATENCY_KEYS},
        "fps": 15.0,
        "counters": {
            "dropped": 0, "overflow": 0, "duplicate": 0,
            "reorder": 0, "timeout": 0, "error": 0,
        },
        "sdr_status": "ok",
        "fpga_status": "ok",
        "npu_status": "ok",
        "spectrum_bins": [0.1] * 128,
    }
    frame["probabilities"][3] = 0.9
    frame.update(overrides)
    return frame


def test_class_order_frozen():
    assert CLASS_NAMES == ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]
    assert class_id_of("BPSK") == 0
    assert class_id_of("OFDM") == 7
    assert class_id_of("nope") == -1


def test_sequence_duplicate():
    m = FrameSequenceMonitor()
    for fid in [1, 1, 1]:
        m.observe(fid)
    assert m.stats.seen == 3
    assert m.stats.duplicate == 2
    assert m.stats.reorder == 0
    assert m.stats.gap == 0
    assert m.stats.dropped == 0


def test_sequence_reorder_then_gap():
    m = FrameSequenceMonitor()
    for fid in [1, 2, 3, 2, 4]:
        m.observe(fid)
    assert m.stats.seen == 5
    assert m.stats.reorder == 1
    assert m.stats.gap == 1
    assert m.stats.dropped == 1
    assert m.stats.last_frame_id == 4


def test_sequence_gap_drop_count():
    m = FrameSequenceMonitor()
    for fid in [1, 5]:
        m.observe(fid)
    assert m.stats.gap == 1
    assert m.stats.dropped == 3


def test_sequence_reset():
    m = FrameSequenceMonitor()
    for fid in [1, 2]:
        m.observe(fid)
    m.reset()
    assert m.stats.seen == 0 and not m.stats.have_last


def test_stale_boundary():
    assert is_stale(100, 200, 50) is True    # 100 ns old > 50 ns
    assert is_stale(160, 200, 50) is False   # 40 ns <= 50 ns
    assert is_stale(200, 200, 50) is False   # exactly at the window (not >)
    assert is_stale(300, 200, 50) is False   # clock skew: now < timestamp
    d = StaleDetector(50)
    assert d.is_stale(100, 200) is True
    assert d.is_stale(160, 200) is False


def test_validate_ok():
    assert validate_frame(make_valid_frame()) == ""


def test_validate_schema_version():
    assert validate_frame(make_valid_frame(schema_version=2)) == "schema_version mismatch"


def test_validate_class_id_out_of_range():
    assert validate_frame(make_valid_frame(class_id=8)) == "class_id out of range"


def test_validate_class_name_mismatch():
    assert validate_frame(make_valid_frame(class_name="QPSK")) == "class_name != class_id"


def test_validate_probabilities_length():
    assert validate_frame(make_valid_frame(probabilities=[0.5] * 7)) == \
        "probabilities must have 8 entries"


def test_validate_confidence_out_of_range():
    assert validate_frame(make_valid_frame(confidence=1.5)) == \
        "confidence must be finite in [0,1]"


def test_validate_nan_snr():
    assert validate_frame(make_valid_frame(snr_db=float("nan"))) == "snr_db non-finite"


def test_validate_negative_latency():
    f = make_valid_frame()
    f["latency_us"]["fpga_process"] = -1.0
    assert validate_frame(f) == "latency non-finite or negative"


def test_validate_spectrum_nan():
    f = make_valid_frame()
    f["spectrum_bins"][0] = math.inf
    assert validate_frame(f) == "spectrum_bins non-finite"
