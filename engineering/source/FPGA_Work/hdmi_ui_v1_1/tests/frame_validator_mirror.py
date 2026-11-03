"""Python mirror of the C++ contract and integrity logic.

Kept line-for-line in sync (manually) with:
  contracts/result_frame.hpp   -> validate(), is_stale(), class-name tables
  src/frame_validator.hpp      -> FrameSequenceMonitor, StaleDetector
  src/json_result_frame.cpp    -> parse_result_frame() (V1.1 + legacy shapes)

This is the host-side executable twin of the Qt-free C++ logic, so the same
invariants are asserted by ``ctest`` (when a Qt/C++ toolchain exists) and by
pytest (always).  ``tests/test_frame_validator_mirror.py``,
``tests/test_json_result_frame.py`` and ``tests/test_mock_data.py`` import it.
"""

from __future__ import annotations

import json
import math

K_CONTRACT_VERSION = 2
K_LEGACY_CONTRACT_VERSION = 1
K_MIN_CLASSES = 8
K_MAX_CLASSES = 16

DEFAULT_CLASS_NAMES = [
    "AM-DSB", "WBFM", "2FSK", "GFSK", "BPSK",
    "QPSK", "8PSK", "16QAM", "64QAM", "OFDM",
]

LEGACY_CLASS_NAMES = [
    "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM",
]


def is_finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def is_stale(timestamp_ns, now_ns, timeout_ns):
    return now_ns >= timestamp_ns and (now_ns - timestamp_ns) > timeout_ns


def validate_frame(f):
    """Mirror of ResultFrame::validate(); "" when valid, else a reason."""
    cv = f.get("contract_version")
    if cv not in (K_CONTRACT_VERSION, K_LEGACY_CONTRACT_VERSION):
        return "contract_version unsupported"
    if cv == K_CONTRACT_VERSION and not f.get("model_id"):
        return "model_id empty"

    names = f.get("class_names", [])
    n = len(names)
    if not (K_MIN_CLASSES <= n <= K_MAX_CLASSES):
        return "class_names length out of [8,16]"
    if any(not c for c in names):
        return "empty class name"
    if len(set(names)) != n:
        return "duplicate class name"

    scores = f.get("scores", [])
    if len(scores) != n:
        return "scores length != class_names length"
    for s in scores:
        if not is_finite(s) or not (0.0 <= s <= 1.0):
            return "score out of [0,1] or non-finite"

    idx = f.get("predicted_index", -1)
    if not (0 <= idx < n):
        return "predicted_index out of range"
    if f.get("predicted_class") != names[idx]:
        return "predicted_class != class_names[predicted_index]"

    conf = f.get("confidence")
    if not is_finite(conf) or not (0.0 <= conf <= 1.0):
        return "confidence must be finite in [0,1]"

    if not is_finite(f.get("snr_db")):
        return "snr_db non-finite"
    if not is_finite(f.get("center_frequency_hz")):
        return "center_frequency_hz non-finite"
    if not is_finite(f.get("sample_rate_hz")):
        return "sample_rate_hz non-finite"
    fps = f.get("fps")
    if not is_finite(fps) or fps < 0.0:
        return "fps invalid"

    l = f.get("latency_us", {})
    for k in ("sdr_capture", "resample_frame", "plddr_transfer",
              "fpga_process", "npu_infer", "end_to_end"):
        v = l.get(k)
        if not is_finite(v) or v < 0.0:
            return "latency non-finite or negative"

    for b in f.get("spectrum_bins", []):
        if not is_finite(b):
            return "spectrum_bins non-finite"
    return ""


class FrameSequenceMonitor:
    """Mirror of FrameSequenceMonitor (duplicate/reorder/gap/dropped)."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.seen = 0
        self.duplicate = 0
        self.reorder = 0
        self.gap = 0
        self.dropped = 0
        self.last_frame_id = 0
        self.have_last = False

    def observe(self, frame_id):
        if not self.have_last:
            self.have_last = True
            self.last_frame_id = frame_id
            self.seen = 1
            return
        self.seen += 1
        if frame_id == self.last_frame_id:
            self.duplicate += 1
        elif frame_id < self.last_frame_id:
            self.reorder += 1
            self.last_frame_id = frame_id
        else:
            jump = frame_id - self.last_frame_id
            if jump > 1:
                self.gap += 1
                self.dropped += jump - 1
            self.last_frame_id = frame_id


class StaleDetector:
    def __init__(self, timeout_ns):
        self._timeout_ns = timeout_ns

    def timeout_ns(self):
        return self._timeout_ns

    def set_timeout_ns(self, ns):
        self._timeout_ns = ns

    def is_stale(self, timestamp_ns, now_ns):
        return is_stale(timestamp_ns, now_ns, self._timeout_ns)


class LineBuffer:
    """Mirror of src/line_buffer.hpp: byte -> JSON-line framer with a strict
    per-line size limit.  ``push`` returns the number of dropped lines."""

    kMaxLineBytes = 65536

    def __init__(self):
        self._pending = ""
        self._lines = []

    def push(self, data):
        drops = 0
        self._pending += data
        while "\n" in self._pending:
            nl = self._pending.index("\n")
            line = self._pending[:nl]
            self._pending = self._pending[nl + 1:]
            if line.endswith("\r"):
                line = line[:-1]
            if len(line) > self.kMaxLineBytes:
                drops += 1
                continue
            self._lines.append(line)
        if len(self._pending) > self.kMaxLineBytes:
            self._pending = ""
            drops += 1
        return drops

    def pop_line(self):
        if not self._lines:
            return None
        return self._lines.pop(0)

    def queued(self):
        return len(self._lines)

    def clear(self):
        self._pending = ""
        self._lines = []


# --- JSON parse mirror (src/json_result_frame.cpp) ---

def _fill_common(f, o):
    f["frame_id"] = o.get("frame_id", 0)
    f["timestamp_ns"] = o.get("timestamp_ns", 0)
    f["source"] = o.get("source", "UNKNOWN")
    f["confidence"] = o.get("confidence")        # missing -> None -> invalid
    f["snr_db"] = o.get("snr_db")                # missing -> None -> invalid
    f["center_frequency_hz"] = o.get("center_frequency_hz", 0.0)
    f["sample_rate_hz"] = o.get("sample_rate_hz", 0.0)
    f["fps"] = o.get("fps")                      # missing -> None -> invalid
    f["sdr_status"] = o.get("sdr_status", "unknown")
    f["fpga_status"] = o.get("fpga_status", "unknown")
    f["npu_status"] = o.get("npu_status", "unknown")
    f["spectrum_bins"] = o.get("spectrum_bins", [])
    f["message"] = o.get("message", "")

    l = o.get("latency_us")
    if isinstance(l, dict):
        f["latency_us"] = {k: l.get(k, 0.0) for k in (
            "sdr_capture", "resample_frame", "plddr_transfer",
            "fpga_process", "npu_infer", "end_to_end")}
    else:
        f["latency_us"] = {}

    c = o.get("counters")
    if isinstance(c, dict):
        f["counters"] = {k: c.get(k, 0) for k in (
            "dropped", "overflow", "duplicate", "reorder", "timeout", "error")}
    else:
        f["counters"] = {}
    return f


def _parse_v1_1(o):
    f = {
        "contract_version": o.get("contract_version", -1),
        "model_id": o.get("model_id", ""),
        "class_names": o.get("class_names", []),
        "scores": o.get("scores", []),
        "predicted_index": o.get("predicted_index", -1),
        "predicted_class": o.get("predicted_class", ""),
    }
    return _fill_common(f, o)


def _parse_legacy(o):
    f = {
        "contract_version": o.get("schema_version", -1),
        "model_id": "",
        "class_names": list(LEGACY_CLASS_NAMES),
        "scores": o.get("probabilities", []),
        "predicted_index": o.get("class_id", -1),
        "predicted_class": o.get("class_name", ""),
    }
    return _fill_common(f, o)


def parse_result_frame(line):
    """Mirror of parse_result_frame(): returns (frame_dict | None, error_string)."""
    if isinstance(line, bytes):
        line = line.decode("utf-8")
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError) as e:
        return None, "json parse: " + str(e)
    if not isinstance(obj, dict):
        return None, "json: root is not an object"

    if "contract_version" in obj:
        f = _parse_v1_1(obj)
    elif "schema_version" in obj:
        f = _parse_legacy(obj)
    else:
        return None, "json: missing contract_version (and legacy schema_version)"

    reason = validate_frame(f)
    if reason:
        return None, "invalid frame: " + reason
    return f, ""
