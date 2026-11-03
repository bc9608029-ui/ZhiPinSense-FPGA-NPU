#!/usr/bin/env python3
"""Deterministic checks for honest recovered-IQ UI measurements."""

from __future__ import annotations

import math
import sys
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CANDIDATES = [
    ROOT / "runtime",
    ROOT / "overlay" / "rml24_final" / "runtime",
    ROOT.parent / "rml24_final_integration1_work" / "runtime",
]
for candidate in reversed(RUNTIME_CANDIDATES):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))

# The delivery contains only the changed ui_event.py, not the frozen receiver
# module.  Supply the immutable 24-label order when the test is run standalone.
try:
    import receiver_core  # noqa: F401
except ModuleNotFoundError:
    receiver_core = types.ModuleType("receiver_core")
    receiver_core.CLASS_NAMES = [
        "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
        "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
        "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
        "AM-DSB-SC", "FM", "GMSK", "OQPSK",
    ]
    sys.modules["receiver_core"] = receiver_core

import ui_event  # noqa: E402


def main() -> None:
    n = np.arange(1024, dtype=np.float64)
    tone = np.exp(2j * np.pi * 37.0 * n / 1024.0)
    tensor = np.empty((8, 2, 1024), dtype=np.float32)
    tensor[:, 0, :] = tone.real
    tensor[:, 1, :] = tone.imag

    logits = [0.0] * 24
    logits[3] = 5.0
    arm = {"pred": 3, "logits": logits, "input_sha256": "0" * 64}
    event = ui_event.build_ui_event(1, arm, timestamp_us=1, display_tensor=tensor)
    result = ui_event.build_board_ui_result(event)
    assert result is not None
    m = result["measurements"]
    assert m is not None
    assert math.isclose(m["model_rms"], 1.0, rel_tol=0.0, abs_tol=1e-5)
    assert abs(m["papr_db"]) < 1e-4
    assert 1 <= m["occupied_bins"] <= 256
    assert 0.0 < m["occupied_bw_hz"] <= 2_560_000.0
    assert abs(m["spectral_centroid_hz"] - 92_500.0) <= 12_000.0

    empty = ui_event.build_ui_event(2, arm, timestamp_us=2, display_tensor=None)
    assert empty["display_measurements"] is None
    assert ui_event.build_board_ui_result(empty)["measurements"] is None
    print("test_ui_measurements: PASS")


if __name__ == "__main__":
    main()
