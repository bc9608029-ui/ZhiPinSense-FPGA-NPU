"""Python mirror of the Qt-free C++ consumer-side integrity layer.

Mirrors, field-for-field and branch-for-branch:

* ``SequenceStats`` / ``FrameSequenceMonitor``  (src/frame_validator.hpp)
* ``StaleDetector``                             (src/frame_validator.hpp)
* ``validate()``                                (contracts/result_frame.hpp)
* ``is_stale()``                                (contracts/result_frame.hpp)

The C++ and this Python module are exercised by the same tests so a drift
between the two languages is caught on the host without a C++ toolchain.
"""

from __future__ import annotations

import math

SCHEMA_VERSION = 1
NUM_CLASSES = 8
CLASS_NAMES = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]
LATENCY_KEYS = [
    "sdr_capture",
    "resample_frame",
    "plddr_transfer",
    "fpga_process",
    "npu_infer",
    "end_to_end",
]


def class_id_of(name):
    for i, n in enumerate(CLASS_NAMES):
        if n == name:
            return i
    return -1


def is_stale(timestamp_ns, now_ns, timeout_ns):
    return now_ns >= timestamp_ns and (now_ns - timestamp_ns) > timeout_ns


class SequenceStats:
    def __init__(self):
        self.seen = 0
        self.duplicate = 0
        self.reorder = 0
        self.gap = 0
        self.dropped = 0
        self.last_frame_id = 0
        self.have_last = False


class FrameSequenceMonitor:
    def __init__(self):
        self.stats = SequenceStats()

    def observe(self, frame_id):
        if not self.stats.have_last:
            self.stats.have_last = True
            self.stats.last_frame_id = frame_id
            self.stats.seen = 1
            return
        self.stats.seen += 1
        if frame_id == self.stats.last_frame_id:
            self.stats.duplicate += 1
        elif frame_id < self.stats.last_frame_id:
            self.stats.reorder += 1
            self.stats.last_frame_id = frame_id
        else:
            jump = frame_id - self.stats.last_frame_id
            if jump > 1:
                self.stats.gap += 1
                self.stats.dropped += jump - 1
            self.stats.last_frame_id = frame_id

    def reset(self):
        self.stats = SequenceStats()


class StaleDetector:
    def __init__(self, timeout_ns):
        self.timeout_ns = timeout_ns

    def is_stale(self, timestamp_ns, now_ns):
        return is_stale(timestamp_ns, now_ns, self.timeout_ns)


def validate_frame(frame):
    """Mirror of hdmiui::validate(). Returns "" when valid, else a reason.

    Only the fields the C++ validate() checks are mirrored here; enum/source
    strictness is the JSON schema's job (test_mock_data.py).
    """
    def finite(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

    if frame.get("schema_version") != SCHEMA_VERSION:
        return "schema_version mismatch"
    cid = frame.get("class_id")
    if not isinstance(cid, int) or isinstance(cid, bool) or not (0 <= cid < NUM_CLASSES):
        return "class_id out of range"
    if class_id_of(frame.get("class_name")) != cid:
        return "class_name != class_id"

    conf = frame.get("confidence")
    if not finite(conf) or conf < 0.0 or conf > 1.0:
        return "confidence must be finite in [0,1]"

    probs = frame.get("probabilities")
    if not isinstance(probs, list) or len(probs) != NUM_CLASSES:
        return "probabilities must have 8 entries"
    for p in probs:
        if not finite(p) or p < 0.0 or p > 1.0:
            return "probability out of [0,1] or non-finite"

    if not finite(frame.get("snr_db")):
        return "snr_db non-finite"
    if not finite(frame.get("center_frequency_hz")):
        return "center_frequency_hz non-finite"
    if not finite(frame.get("sample_rate_hz")):
        return "sample_rate_hz non-finite"

    fps = frame.get("fps")
    if not finite(fps) or fps < 0.0:
        return "fps invalid"

    lat = frame.get("latency_us") or {}
    for k in LATENCY_KEYS:
        v = lat.get(k)
        if not finite(v) or v < 0.0:
            return "latency non-finite or negative"

    for b in frame.get("spectrum_bins", []):
        if not finite(b):
            return "spectrum_bins non-finite"

    return ""
