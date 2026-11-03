"""Frozen RadioML2018.01A 24-class contract for M25-B (self-contained).

Mirrors the frozen constants from ``sdr_amr_rml24_ood_v1_1/contracts/rml24_contract.py``
WITHOUT importing that project at runtime.  The 24-label order, I/O contract, and
dataset SHAs are authoritative and frozen.  Nothing here may be changed to make
training easier.
"""
from __future__ import annotations

from typing import Iterable

# Frozen 24-class label order (authoritative; never reorder).
LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)

# Twelve-class board deployment order (12<->24 body reference only).
LABEL_ORDER_12 = (
    "OOK", "4ASK", "AM-DSB", "WBFM", "2FSK", "GFSK",
    "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "OFDM",
)

# Deployment I/O contract.  RadioML2018.01A samples are per-sample unit-RMS
# (measured ~1.0002 +- 0.0125); no re-scaling.  Output is raw logits, no softmax,
# and there is NO stride-2048 in this input contract.
INPUT_SHAPE = (1, 2, 1024)
OUTPUT_DIM = 24
OUTPUT_KIND = "raw_logits_no_softmax"

# Frozen dataset / label-file SHAs (read-only ground truth).
DATASET_HDF5_SHA256 = "e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38"
DATASET_INDEX_SHA256 = "9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335"
CLASSES_TXT_SHA256 = "0814d7b5a522abacd1eb3052f89fb83a8e91f83cf53745e5a6b804dd1b85e3c8"

# Current 12-class production model raw SHA (reference only; never overwritten).
TWELVE_CLASS_MODEL_SHA256 = "2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c"

# Highest statuses this pre-research framework may reach.
BASELINE_NOT_FROZEN_MARKER = "24CLASS_BASELINE_NOT_FROZEN"
OE_MODEL_NOT_TRAINED_MARKER = "24CLASS_OE_MODEL_NOT_TRAINED"
OE_FRAMEWORK_READY_MARKER = "24CLASS_OE_FRAMEWORK_READY"

# Status markers that must never be written before real NPU + real RF verification.
FORBIDDEN_STATUS_MARKERS = (
    "FINAL_MODEL_PASS", "FINAL_24CLASS_PASS", "OOD_PASS", "HARDWARE_PASS",
    "FULL_CHAIN_PASS", "PROJECT_COMPLETE", "DEPLOYMENT_PASS", "PERFORMANCE_PASS",
    "24CLASS_OE_PASS", "24CLASS_OE_HARDWARE_PASS", "TEMPORAL_FUSION_HARDWARE_PASS",
)


def assert_24class_order(names: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(str(value).upper() for value in names)
    if normalized != LABEL_ORDER_24:
        raise ValueError(
            f"24-class contract requires frozen order {LABEL_ORDER_24}, got {normalized}"
        )
    return normalized


def assert_not_final_status(status: str) -> None:
    if status in FORBIDDEN_STATUS_MARKERS:
        raise RuntimeError(
            f"forbidden final status marker {status!r}; real RF/NPU not yet verified"
        )
