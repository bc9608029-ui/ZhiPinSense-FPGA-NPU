"""Canonical fail-closed event adapter for the final 7-inch UI."""

from __future__ import annotations

import math
import time
from typing import Any

import numpy as np

from receiver_core import CLASS_NAMES


VERSION = "rml24-final-ui-v1"
MODEL_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"


def _display_payload(tensor: np.ndarray | None) -> dict[str, Any]:
    """Build compact, honest display data from the same recovered model tensor."""
    empty = {
        "iq_valid": False,
        "iq_i16_interleaved": None,
        "iq_units_per_count": None,
        "spectrum_valid": False,
        "spectrum_db_rel_x4": None,
    }
    if tensor is None:
        return empty
    value = np.asarray(tensor)
    if value.shape != (8, 2, 1024) or not np.isfinite(value).all():
        return empty

    # The eight windows are repetitions of one public-frame payload. Averaging
    # is display-only; inference still runs all windows and averages logits.
    complex_windows = value[:, 0, :] + 1j * value[:, 1, :]
    display_iq = complex_windows.mean(axis=0, dtype=np.complex128)
    points = display_iq[::4]
    peak = float(max(np.max(np.abs(points.real)), np.max(np.abs(points.imag))))
    if not math.isfinite(peak) or peak <= 0.0:
        return empty
    units_per_count = peak / 30000.0
    interleaved = np.empty(512, dtype=np.int16)
    interleaved[0::2] = np.rint(points.real / units_per_count).clip(-30000, 30000).astype(np.int16)
    interleaved[1::2] = np.rint(points.imag / units_per_count).clip(-30000, 30000).astype(np.int16)

    windowed = display_iq * np.hanning(1024)
    power = np.abs(np.fft.fftshift(np.fft.fft(windowed))) ** 2
    power_256 = power.reshape(256, 4).mean(axis=1)
    floor = max(float(power_256.max()) * 1e-8, np.finfo(np.float64).tiny)
    db_rel = 10.0 * np.log10(np.maximum(power_256, floor) / max(float(power_256.max()), floor))
    spectrum_x4 = np.rint(db_rel * 4.0).clip(-320, 0).astype(np.int16)
    return {
        "iq_valid": True,
        "iq_i16_interleaved": interleaved.astype(int).tolist(),
        "iq_units_per_count": units_per_count,
        "spectrum_valid": True,
        "spectrum_db_rel_x4": spectrum_x4.astype(int).tolist(),
    }


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
    display_tensor: np.ndarray | None = None,
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
        "self_test": self_test,
    }
    event.update(_display_payload(display_tensor))
    validate_ui_event(event)
    return event


def validate_ui_event(event: dict[str, Any]) -> None:
    required = {
        "type", "version", "frame_id", "timestamp_us", "state", "class_count",
        "prediction", "model_input_sha256", "measurements", "iq_valid",
        "iq_i16_interleaved", "iq_units_per_count", "spectrum_valid",
        "spectrum_db_rel_x4", "self_test",
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
    if event["iq_valid"]:
        points = event["iq_i16_interleaved"]
        scale = event["iq_units_per_count"]
        if not isinstance(points, list) or len(points) != 512 or not all(isinstance(value, int) and -30000 <= value <= 30000 for value in points):
            raise ValueError("iq_valid requires 256 interleaved int16 points")
        if not isinstance(scale, (float, int)) or not math.isfinite(float(scale)) or float(scale) <= 0:
            raise ValueError("iq_valid requires positive IQ scale")
    elif event["iq_i16_interleaved"] is not None or event["iq_units_per_count"] is not None:
        raise ValueError("invalid IQ payload must be null")
    if event["spectrum_valid"]:
        bins = event["spectrum_db_rel_x4"]
        if not isinstance(bins, list) or len(bins) != 256 or not all(isinstance(value, int) and -320 <= value <= 0 for value in bins):
            raise ValueError("spectrum_valid requires 256 bins")
    elif event["spectrum_db_rel_x4"] is not None:
        raise ValueError("invalid spectrum payload must be null")


def build_board_ui_result(event: dict[str, Any]) -> dict[str, Any] | None:
    """Flatten a canonical event for the existing framebuffer parser family."""
    validate_ui_event(event)
    prediction = event["prediction"]
    if prediction is None:
        return None
    measurements = None
    if event["spectrum_valid"]:
        measurements = {
            "spectrum_valid": True,
            "spectrum_fft_length": 1024,
            "spectrum_bin_count": 256,
            "spectrum_sample_rate_hz": 2_560_000,
            "spectrum_center_hz": 2_400_000_000,
            # The legacy renderer field is named dbfs, but these values are
            # explicitly relative-to-peak in the final schema and screen label.
            "spectrum_dbfs_x4": event["spectrum_db_rel_x4"],
        }
    return {
        "type": "result",
        "version": "rml24-final-chain-v1",
        "frame_id": event["frame_id"],
        "timestamp_us": event["timestamp_us"],
        "model_mode": "RML24-BF16-RAW",
        "class_count": 24,
        "argmax_idx": prediction["index"],
        "argmax_class": prediction["class_name"],
        "confidence": prediction["confidence"],
        "merged_23_top1": -1,
        "raw_24_top1": prediction["index"],
        "deployment_mode": "RAW24_UNMERGED",
        "expert_enabled": False,
        "expert_result": "NOT_RUN",
        "probabilities": prediction["probabilities"],
        "snr_db": None,
        "quality": prediction["confidence"],
        "model_sha": MODEL_SHA,
        "mock": False,
        "source": "rml24_final_receiver",
        "e2e_us": 0.0,
        "preprocess_us": 0.0,
        "classify_us": 0.0,
        "overflow": False,
        "dropped": False,
        "discontinuity": False,
        "short_frame": False,
        "presence_state": "SIGNAL_PRESENT",
        "level_mode": "FIXED",
        "model_scale": 1.0,
        "rf_gain_db": 35.0,
        "work_mode": "FIXED",
        "run_state": "RUNNING",
        "measurements": measurements,
        "iq_valid": event["iq_valid"],
        "iq_i16_interleaved": event["iq_i16_interleaved"],
        "iq_units_per_count": event["iq_units_per_count"],
    }

