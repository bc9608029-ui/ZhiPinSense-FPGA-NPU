"""Frozen twelve-class contract and red lines for the V2 robustness task.

The label order, I/O contract, and V1 identity are frozen.  Nothing here may be
changed to make training easier; the board input layout is authoritative.
"""

from __future__ import annotations

from typing import Any

# Frozen twelve-class label order (authoritative; never reorder).
LABEL_ORDER_12 = (
    "OOK", "4ASK", "AM-DSB", "WBFM", "2FSK", "GFSK",
    "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "OFDM",
)

# Frozen V1 identity.  V2 candidates never overwrite this model.
V1_MODEL_NAME = "12CLASS_CHAIN_VALIDATION_MODEL_V1"
V1_MODEL_SHA = "2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c"
V2_MODEL_NAME = "12CLASS_ROBUST_CANDIDATE_V2"

# Deployment I/O contract (read from V1; never changed for training convenience).
INPUT_SHAPE = (1, 2, 1024)  # fp32, RMS 1.0, [real, imag]
OUTPUT_DIM = 12

# Markers that must never be written before real NPU + real RF verification.
FORBIDDEN_STATUS_MARKERS = (
    "FINAL_MODEL_PASS", "ROBUST_MODEL_PASS", "REAL_RF_PASS",
    "OOD_PASS", "PROJECT_COMPLETE",
)


def assert_12class_contract(signal_config: dict[str, Any]) -> None:
    classes = tuple(str(v).upper() for v in signal_config["modulations"])
    if classes != LABEL_ORDER_12:
        raise ValueError(f"V2 requires frozen twelve-class order {LABEL_ORDER_12}, got {classes}")
    if int(signal_config.get("sample_length", 1024)) != 1024:
        raise ValueError("V2 deployment contract requires sample_length=1024")


def assert_not_final_status(status: str) -> None:
    if status in FORBIDDEN_STATUS_MARKERS:
        raise RuntimeError(f"forbidden final status marker {status!r}; real RF/NPU not yet verified")
