"""Canonical fail-closed event adapter for the final 7-inch UI."""

from __future__ import annotations

import math
import time
from typing import Any

import numpy as np

from receiver_core import CLASS_NAMES


VERSION = "rml24-final-ui-v1"


def _prediction_from_arm(arm: dict[str, Any]) -> dict[str, Any] | None:
    pred = arm.get("pred", -1)
    logits = arm.get("logits") or arm.get("mean_logits")
    if not isinstance(pred, int) or not (0 <= pred < 24) or not isinstance(logits, list) or len(logits) != 24:
        return None
    values = np.asarray(logits, dtype=np.float64)
    if not np.isfinite(values).all():
        return None
    weights = np.exp(values - values.max())
    probabilities = weights / weights.sum()
    top3 = np.argsort(values)[::-1][:3]
    return {
        "index": pred,
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
        "probabilities": probabilities.astype(float).tolist(),
    }


def build_ui_event(
    frame_id: int,
    arm: dict[str, Any],
    *,
    timestamp_us: int | None = None,
    confidence_threshold: float = 0.55,
    self_test: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prediction = _prediction_from_arm(arm)
    if prediction is None:
        state = "RECOVERY_FAILED"
    elif prediction["confidence"] < confidence_threshold:
        state = "LOW_CONFIDENCE"
    else:
        state = "IDENTIFIED"

    measurement_names = (
        "cfo_hz",
        "training_residual",
        "fir_training_residual",
        "head_reference_relative_error",
        "tail_reference_relative_error",
        "tail_residual",
        "gain",
        "dc",
    )
    measurements = {}
    for name in measurement_names:
        if name in arm:
            value = float(arm[name])
            if math.isfinite(value):
                measurements[name] = value

    digest = arm.get("input_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        digest = None
    event = {
        "type": "rml24_ui_frame",
        "version": VERSION,
        "frame_id": int(frame_id),
        "timestamp_us": int(time.time_ns() // 1000 if timestamp_us is None else timestamp_us),
        "state": state,
        "class_count": 24,
        "prediction": prediction,
        "model_input_sha256": digest,
        "measurements": measurements,
        "iq_valid": False,
        "iq_file": None,
        "spectrum_valid": False,
        "spectrum_dbfs_x4": None,
        "self_test": self_test,
    }
    validate_ui_event(event)
    return event


def validate_ui_event(event: dict[str, Any]) -> None:
    required = {
        "type", "version", "frame_id", "timestamp_us", "state", "class_count",
        "prediction", "model_input_sha256", "measurements", "iq_valid",
        "iq_file", "spectrum_valid", "spectrum_dbfs_x4", "self_test",
    }
    if set(event) != required:
        raise ValueError(f"UI event keys differ: {sorted(set(event) ^ required)}")
    if event["type"] != "rml24_ui_frame" or event["version"] != VERSION or event["class_count"] != 24:
        raise ValueError("UI event identity mismatch")
    if event["state"] not in {"ACQUIRING", "IDENTIFIED", "LOW_CONFIDENCE", "RECOVERY_FAILED", "NO_SIGNAL", "STOPPED"}:
        raise ValueError("unknown UI state")
    prediction = event["prediction"]
    if prediction is None:
        if event["state"] in {"IDENTIFIED", "LOW_CONFIDENCE"}:
            raise ValueError("classification state requires prediction")
    else:
        if set(prediction) != {"index", "class_name", "confidence", "top3", "probabilities"}:
            raise ValueError("prediction keys differ")
        index = prediction["index"]
        probabilities = prediction["probabilities"]
        if not isinstance(index, int) or not 0 <= index < 24 or prediction["class_name"] != CLASS_NAMES[index]:
            raise ValueError("prediction identity mismatch")
        if len(probabilities) != 24 or not all(math.isfinite(float(value)) and 0 <= float(value) <= 1 for value in probabilities):
            raise ValueError("invalid probabilities")
        if abs(sum(probabilities) - 1.0) > 1e-6:
            raise ValueError("probabilities do not sum to one")
        if len(prediction["top3"]) != 3:
            raise ValueError("top3 length must be three")
    if event["iq_valid"] and not event["iq_file"]:
        raise ValueError("iq_valid requires iq_file")
    if event["spectrum_valid"]:
        bins = event["spectrum_dbfs_x4"]
        if not isinstance(bins, list) or len(bins) != 256:
            raise ValueError("spectrum_valid requires 256 bins")

