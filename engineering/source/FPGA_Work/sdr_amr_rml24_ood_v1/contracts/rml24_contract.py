"""Frozen RadioML2018.01A 24-class contract and red lines.

The 24-label order, I/O contract, and model naming are frozen.  Nothing here may
be changed to make training easier; the RadioML2018.01A label order (verified
against ``datasets.radioml2018_dataset.OFFICIAL_CLASS_ORDER``) and the board input
layout are authoritative.
"""

from __future__ import annotations

from typing import Any, Iterable

# Frozen 24-class label order (authoritative; never reorder).  Matches
# datasets.radioml2018_dataset.OFFICIAL_CLASS_ORDER exactly.
LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)

# Model names.  A candidate never adopts the benchmark name, and no name here is
# ever promoted to a "FINAL/PASS" marker before real NPU + real RF verification.
RML24_MODEL_NAME = "RML2018_24_BENCHMARK"
RML24_ROBUST_MODEL_NAME = "RML2018_24_ROBUST_CANDIDATE"

# Deployment I/O contract.  RadioML2018.01A samples are already per-sample
# normalized to unit RMS (measured ~1.0002 +- 0.0125), so no re-scaling is
# applied; this matches the 12-class board RMS-1.0 contract.
INPUT_SHAPE = (1, 2, 1024)  # fp32, [real, imag], RMS ~1.0
OUTPUT_DIM = 24
OUTPUT_KIND = "raw_logits_no_softmax"

# Twelve-class model import contract (filled only after the 12-class V2
# checkpoint is trained; the SHA/checkpoint path are placeholders until then).
TWELVE_CLASS_MODEL_NAME = "12CLASS_ROBUST_CANDIDATE_V2"
TWELVE_CLASS_CHECKPOINT_PENDING = "PENDING_12CLASS_V2_CHECKPOINT"
TWELVE_CLASS_SHA_PENDING = "PENDING_12CLASS_V2_SHA256"

# OOD working points (frozen names; balanced is the default).
OOD_WORKING_POINTS = ("conservative", "balanced", "strict")

# Status markers that must never be written before real NPU + real RF verification.
FORBIDDEN_STATUS_MARKERS = (
    "FINAL_MODEL_PASS", "FINAL_24CLASS_PASS", "OOD_PASS",
    "HARDWARE_PASS", "FULL_CHAIN_PASS", "PROJECT_COMPLETE",
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
        raise RuntimeError(f"forbidden final status marker {status!r}; real RF/NPU not yet verified")


def rml24_model_payload(model_name: str, epoch: int, best_score: float,
                        best_epoch: int, stale_epochs: int,
                        history: list[dict[str, Any]], classes: list[str],
                        loss_name: str, config: dict[str, Any],
                        model_state: dict[str, Any], optimizer_state: dict[str, Any],
                        scheduler_state: dict[str, Any], amp_state: dict[str, Any]) -> dict[str, Any]:
    """Construct a 24-class checkpoint payload (V2-compatible keys + 24-class name)."""
    return {
        "checkpoint_version": 2,
        "model_name": model_name,
        "epoch": epoch,
        "next_epoch": epoch + 1,
        "model_state": model_state,
        "optimizer_state": optimizer_state,
        "scheduler_state": scheduler_state,
        "amp_state": amp_state,
        "best_selection_score": best_score,
        "best_epoch": best_epoch,
        "stale_epochs": stale_epochs,
        "history": history,
        "class_names": classes,
        "loss_name": loss_name,
        "rml24": config.get("rml24", {}),
        "v2": config.get("v2", {}),
    }
