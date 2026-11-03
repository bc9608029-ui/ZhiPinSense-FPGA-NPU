"""Label-blind production core shared by live capture and raw replay."""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import numpy as np


CLASS_NAMES = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)


@dataclass(frozen=True)
class RecoveredFrame:
    tensor: np.ndarray
    tensor_bytes: bytes
    tensor_sha256: str
    metadata: dict[str, float]


def tensorize(windows: np.ndarray) -> tuple[np.ndarray, bytes, str]:
    """Convert 8 complex windows to the frozen [8, 2, 1024] LE-f32 tensor."""
    windows = np.asarray(windows)
    if windows.shape != (8, 1024):
        raise ValueError(f"recovered window shape must be (8, 1024), got {windows.shape}")
    if not np.isfinite(windows.real).all() or not np.isfinite(windows.imag).all():
        raise ValueError("recovered windows contain non-finite values")
    tensor = np.stack([windows.real, windows.imag], axis=1).astype("<f4", copy=False)
    if tensor.shape != (8, 2, 1024):
        raise AssertionError(tensor.shape)
    data = tensor.tobytes(order="C")
    return tensor, data, hashlib.sha256(data).hexdigest()


def recover_frame(raw_iq: np.ndarray, recover: Callable[[np.ndarray], tuple[np.ndarray, dict[str, Any]]]) -> RecoveredFrame:
    raw_iq = np.asarray(raw_iq)
    if raw_iq.ndim != 1 or not np.iscomplexobj(raw_iq):
        raise ValueError("raw IQ must be a one-dimensional complex array")
    if not np.isfinite(raw_iq.real).all() or not np.isfinite(raw_iq.imag).all():
        raise ValueError("raw IQ contains non-finite values")
    windows, metadata = recover(raw_iq)
    tensor, data, digest = tensorize(windows)
    clean_meta: dict[str, float] = {}
    for key, value in metadata.items():
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"recovery metadata {key!r} is non-finite")
        clean_meta[str(key)] = value
    return RecoveredFrame(tensor=tensor, tensor_bytes=data, tensor_sha256=digest, metadata=clean_meta)


def summarize_logits(logit_rows: Iterable[np.ndarray]) -> dict[str, Any]:
    logits = np.asarray(list(logit_rows), dtype=np.float32)
    if logits.shape != (8, 24):
        raise ValueError(f"logits must have shape (8, 24), got {logits.shape}")
    if not np.isfinite(logits).all():
        raise ValueError("logits contain non-finite values")
    mean_logits = logits.mean(axis=0, dtype=np.float64)
    pred = int(np.argmax(mean_logits))
    shifted = mean_logits - np.max(mean_logits)
    probabilities = np.exp(shifted)
    probabilities /= probabilities.sum()
    top3 = np.argsort(mean_logits)[::-1][:3]
    return {
        "pred": pred,
        "class_name": CLASS_NAMES[pred],
        "confidence": float(probabilities[pred]),
        "top3": [
            {
                "index": int(index),
                "class_name": CLASS_NAMES[int(index)],
                "probability": float(probabilities[int(index)]),
            }
            for index in top3
        ],
        "window_predictions": logits.argmax(axis=1).astype(int).tolist(),
        "mean_logits": mean_logits.astype(float).tolist(),
    }

