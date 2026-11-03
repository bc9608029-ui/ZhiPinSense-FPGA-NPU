"""Frozen M20 12-class OOD-U contract (single source of truth).

Nothing here may be changed to make the task easier.  The label order, model
identity, I/O contract, OOD families, score methods, and working points are all
frozen and cross-checked against the authoritative deployment contract
(``model_12class/MODEL_DEPLOYMENT_CONTRACT.md``) and the generator's frozen
12-class order (``datasets.modulation_generator.V1_1_12_MODULATIONS``).
"""

from __future__ import annotations

from typing import Iterable

# --- Model identity (authoritative, SHA-verified in docs/M20_MODEL_OUTPUT_AUDIT.md)
MODEL_NAME = "12CLASS_CHAIN_VALIDATION_MODEL"
# The task's authoritative ``model_sha`` — the iCraft int8-compiled NPU weights.
MODEL_SHA256 = "2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c"
# Upstream fp32 checkpoint (deployment weight source, epoch 22).
CHECKPOINT_SHA256 = "7215290b0f43f8a8cc05f4ee135f2a9524cf8a8036b71ae52b0b6c94c02aae72"
# Source ONNX (opset 17 / IR 8, fp32).
ONNX_SHA256 = "f77587152b52cda9a467b28790bc62d0eb0c639db2c39da82642c00ca8deda5a"
# iCraft compiled graph (op_id 180 output @fp(32) [1,12] @hostt).
NPU_JSON_SHA256 = "51364bdf49d280944094f7af89ea4c759b3ae4d0d350be5f8c43e0c5849ab834"

# --- I/O contract
LABEL_ORDER_12: tuple[str, ...] = (
    "OOK", "4ASK", "AM-DSB", "WBFM", "2FSK", "GFSK",
    "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "OFDM",
)
INPUT_SHAPE = (1, 2, 1024)  # fp32 planar I/Q, RMS ~1.0, no input quantization
OUTPUT_DIM = 12
OUTPUT_NUMERIC_TYPE = "fp32"
OUTPUT_KIND = "raw_logits_no_softmax"
# The output boundary carries no quantized type: no scale / no zero-point.
OUTPUT_SCALE: float | None = None
OUTPUT_ZERO_POINT: int | None = None

# --- Score methods (frozen; exactly the five mandated, all "higher = more OOD")
SCORE_METHODS: tuple[str, ...] = ("msp", "entropy", "max_logit", "logit_margin", "energy")
DIRECTION = "higher_is_ood"

# --- Frozen working points (M20-specific names; id_accept_99 is the default).
WORKING_POINT_ID_ACCEPT_95 = "id_accept_95"
WORKING_POINT_ID_ACCEPT_99 = "id_accept_99"
WORKING_POINT_FAR_OOD = "far_ood_target"
WORKING_POINTS: tuple[str, ...] = (
    WORKING_POINT_ID_ACCEPT_95, WORKING_POINT_ID_ACCEPT_99, WORKING_POINT_FAR_OOD,
)
DEFAULT_WORKING_POINT = WORKING_POINT_ID_ACCEPT_99

# --- Protocol domain (frozen; ID and OOD share the same signal + channel domain)
SAMPLE_RATE_HZ = 128_000.0
SYMBOL_RATE_HZ = 16_000.0
SAMPLES_PER_SYMBOL = 8
SAMPLE_LENGTH = 1024
AMPLITUDE = 1.0
ROLLOFF = 0.35
SPAN_SYMBOLS = 8
# Core semantic-OOD-U benchmark SNR sweep (documented: the regime where semantic
# OOD is crisp).  Low-SNR known classes (-20..-10 dB) are *OOD-R*, handled by the
# protection test, never used to inflate the OOD threshold.
BENCHMARK_SNR_VALUES: tuple[float, ...] = (0.0, 10.0, 20.0)

# --- Data isolation seeds (distinct from the model's own training seeds)
OOD_SEED = 12_600  # base seed for the 12-class OOD-U generator namespace

# --- Status red lines (never written before real NPU + real RF verification)
FORBIDDEN_STATUS_MARKERS: tuple[str, ...] = (
    "OOD_PASS", "HARDWARE_PASS", "PROJECT_COMPLETE", "FINAL_MODEL_PASS",
    "OOD_U_PASS", "DEPLOYMENT_PASS",
)

# --- Decision sentinels (mirror cpp/ood_u_contract.hpp).  UNKNOWN is the OOD-U
# rejection label and must stay distinct from NO_SIGNAL (no input) and ERROR
# (non-finite logits), and from every known class name.
UNKNOWN = "UNKNOWN"
NO_SIGNAL = "NO_SIGNAL"
ERROR = "ERROR"
EMPTY = ""


def assert_12class_order(names: Iterable[str]) -> tuple[str, ...]:
    """Fail-closed: the 12-class order must match the frozen contract exactly."""
    normalized = tuple(str(value).upper() for value in names)
    if normalized != LABEL_ORDER_12:
        raise ValueError(
            f"12-class contract requires frozen order {LABEL_ORDER_12}, got {normalized}"
        )
    return normalized


def assert_logits_12(logits: object) -> None:
    """Fail-closed: logits must be finite [N, 12] (dimension error => raise)."""
    import numpy as np

    arr = np.asarray(logits, dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != OUTPUT_DIM:
        raise ValueError(
            f"OOD-U requires logits [N, {OUTPUT_DIM}], got shape {arr.shape}"
        )
    if not np.isfinite(arr).all():
        raise ValueError("logits contain non-finite (NaN/Inf) values; refusing to score")


def assert_not_final_status(status: str) -> None:
    if status in FORBIDDEN_STATUS_MARKERS:
        raise RuntimeError(f"forbidden final status marker {status!r}; real NPU/RF not yet verified")


__all__ = [
    "MODEL_NAME", "MODEL_SHA256", "CHECKPOINT_SHA256", "ONNX_SHA256", "NPU_JSON_SHA256",
    "LABEL_ORDER_12", "INPUT_SHAPE", "OUTPUT_DIM", "OUTPUT_NUMERIC_TYPE", "OUTPUT_KIND",
    "OUTPUT_SCALE", "OUTPUT_ZERO_POINT", "SCORE_METHODS", "DIRECTION",
    "WORKING_POINTS", "DEFAULT_WORKING_POINT",
    "WORKING_POINT_ID_ACCEPT_95", "WORKING_POINT_ID_ACCEPT_99", "WORKING_POINT_FAR_OOD",
    "SAMPLE_RATE_HZ", "SYMBOL_RATE_HZ", "SAMPLES_PER_SYMBOL", "SAMPLE_LENGTH",
    "AMPLITUDE", "ROLLOFF", "SPAN_SYMBOLS", "BENCHMARK_SNR_VALUES", "OOD_SEED",
    "FORBIDDEN_STATUS_MARKERS", "assert_12class_order", "assert_logits_12",
    "assert_not_final_status", "UNKNOWN", "NO_SIGNAL", "ERROR", "EMPTY",
]
