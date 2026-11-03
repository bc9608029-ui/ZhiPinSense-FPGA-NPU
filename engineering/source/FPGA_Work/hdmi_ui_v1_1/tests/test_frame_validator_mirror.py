"""Mirrors tests/test_contract.cpp, test_sequence_monitor.cpp, test_stale.cpp.

Exercises the pure-Python twin of contracts/result_frame.hpp and
src/frame_validator.hpp.  The C++ twins assert the same facts under ctest.
"""

from __future__ import annotations

import math

from frame_validator_mirror import (
    DEFAULT_CLASS_NAMES,
    LEGACY_CLASS_NAMES,
    K_CONTRACT_VERSION,
    K_LEGACY_CONTRACT_VERSION,
    FrameSequenceMonitor,
    LineBuffer,
    StaleDetector,
    is_stale,
    validate_frame,
)


def make_good_frame():
    scores = [0.01] * 10
    scores[7] = 0.9
    scores[8] = 0.02
    return {
        "contract_version": K_CONTRACT_VERSION,
        "model_id": "m",
        "frame_id": 5,
        "timestamp_ns": 1,
        "source": "MOCK",
        "class_names": list(DEFAULT_CLASS_NAMES),
        "scores": scores,
        "predicted_index": 7,
        "predicted_class": "16QAM",
        "confidence": 0.9,
        "snr_db": 18.0,
        "center_frequency_hz": 2400000000.0,
        "sample_rate_hz": 128000.0,
        "latency_us": {"sdr_capture": 1, "resample_frame": 1, "plddr_transfer": 1,
                       "fpga_process": 1, "npu_infer": 1, "end_to_end": 5},
        "fps": 15.0,
        "counters": {"dropped": 0, "overflow": 0, "duplicate": 0,
                     "reorder": 0, "timeout": 0, "error": 0},
        "sdr_status": "ok", "fpga_status": "ok", "npu_status": "ok",
        "spectrum_bins": [],
        "message": "",
    }


def test_good_frame_valid():
    assert validate_frame(make_good_frame()) == ""


def test_class_names_order():
    assert DEFAULT_CLASS_NAMES == ["AM-DSB", "WBFM", "2FSK", "GFSK", "BPSK",
                                   "QPSK", "8PSK", "16QAM", "64QAM", "OFDM"]
    assert LEGACY_CLASS_NAMES == ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM",
                                  "2FSK", "CPFSK", "OFDM"]


def test_contract_version_unsupported():
    f = make_good_frame()
    f["contract_version"] = 3
    assert validate_frame(f) == "contract_version unsupported"


def test_v1_1_model_id_required():
    f = make_good_frame()
    f["model_id"] = ""
    assert validate_frame(f) == "model_id empty"


def test_legacy_empty_model_id_ok():
    f = make_good_frame()
    f["contract_version"] = K_LEGACY_CONTRACT_VERSION
    f["model_id"] = ""
    assert validate_frame(f) == ""


def test_predicted_class_mismatch():
    f = make_good_frame()
    f["predicted_class"] = "QPSK"
    assert validate_frame(f) == "predicted_class != class_names[predicted_index]"


def test_confidence_out_of_range():
    f = make_good_frame()
    f["confidence"] = 1.5
    assert validate_frame(f) == "confidence must be finite in [0,1]"


def test_snr_nan_rejected():
    f = make_good_frame()
    f["snr_db"] = float("nan")
    assert validate_frame(f) == "snr_db non-finite"


def test_empty_class_name():
    f = make_good_frame()
    f["class_names"][3] = ""
    assert validate_frame(f) == "empty class name"


def test_duplicate_class_name():
    f = make_good_frame()
    f["class_names"][3] = f["class_names"][0]
    assert validate_frame(f) == "duplicate class name"


def test_scores_length_mismatch():
    f = make_good_frame()
    f["scores"] = f["scores"][:8]
    assert validate_frame(f) == "scores length != class_names length"


def test_too_few_classes():
    f = make_good_frame()
    f["class_names"] = f["class_names"][:7]
    f["scores"] = f["scores"][:7]
    assert validate_frame(f) == "class_names length out of [8,16]"


def test_predicted_index_out_of_range():
    f = make_good_frame()
    f["predicted_index"] = 10
    assert validate_frame(f) == "predicted_index out of range"


# --- sequence monitor (mirrors test_sequence_monitor.cpp) ---

def test_sequence_monitor_first_frame_seeds():
    m = FrameSequenceMonitor()
    m.observe(10)
    assert m.seen == 1 and m.have_last
    assert m.duplicate == 0 and m.reorder == 0 and m.dropped == 0 and m.gap == 0


def test_sequence_monitor_duplicate():
    m = FrameSequenceMonitor()
    m.observe(10)
    m.observe(10)
    m.observe(10)
    assert m.duplicate == 2


def test_sequence_monitor_reorder():
    m = FrameSequenceMonitor()
    for fid in (1, 2, 3, 2):
        m.observe(fid)
    assert m.reorder == 1
    assert m.last_frame_id == 2


def test_sequence_monitor_gap_and_dropped():
    m = FrameSequenceMonitor()
    for fid in (1, 2, 3, 2, 4):
        m.observe(fid)
    assert m.gap == 1 and m.dropped == 1
    m.observe(10)
    assert m.dropped == 1 + 5 and m.gap == 2


# --- staleness (mirrors test_stale.cpp) ---

def test_is_stale_boundaries():
    assert is_stale(100, 200, 50)
    assert not is_stale(160, 200, 50)
    assert not is_stale(200, 200, 50)
    assert not is_stale(300, 200, 50)


def test_stale_detector():
    d = StaleDetector(1500000000)
    assert d.timeout_ns() == 1500000000
    assert d.is_stale(1000, 2000000000)
    assert not d.is_stale(1000, 500000000)
    d.set_timeout_ns(1000)
    assert d.timeout_ns() == 1000
    assert d.is_stale(0, 2000)


# --- line framer (mirrors test_line_buffer.cpp) ---

def test_line_buffer_two_lines():
    b = LineBuffer()
    assert b.push("a\nb\n") == 0
    assert b.pop_line() == "a"
    assert b.pop_line() == "b"
    assert b.pop_line() is None


def test_line_buffer_split_push():
    b = LineBuffer()
    assert b.push("hel") == 0
    assert b.pop_line() is None
    assert b.push("lo\n") == 0
    assert b.pop_line() == "hello"


def test_line_buffer_crlf():
    b = LineBuffer()
    assert b.push("x\r\ny\n") == 0
    assert b.pop_line() == "x"
    assert b.pop_line() == "y"


def test_line_buffer_oversized_complete():
    b = LineBuffer()
    big = "z" * (LineBuffer.kMaxLineBytes + 1)
    assert b.push(big + "\nok\n") == 1
    assert b.pop_line() == "ok"
    assert b.pop_line() is None


def test_line_buffer_oversized_partial():
    b = LineBuffer()
    big = "z" * (LineBuffer.kMaxLineBytes + 10)
    assert b.push(big) == 1
    assert b.push("next\n") == 0
    assert b.pop_line() == "next"
