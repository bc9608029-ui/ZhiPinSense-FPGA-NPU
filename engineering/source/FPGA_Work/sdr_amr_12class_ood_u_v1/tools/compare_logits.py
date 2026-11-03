"""Logits comparison for the NPU parity check (PyTorch / ONNX / NPU).

Two fp32 columns (PyTorch and ONNX) are compared with a tight tolerance; the
int8-NPU column is compared against fp32 with a loose tolerance that accounts
for one quantization step at the observed output-boundary scale (plus margin).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from ood_u import contract

# Tight tolerance for fp32-vs-fp32 (PyTorch vs ONNX, same opset/weights).
FP32_MAX_ABS_DIFF = 1e-4
# Loose tolerance for int8-NPU vs fp32: one quantization step at the observed
# output boundary scale (0.23273507), plus a safety margin.
NPU_MAX_ABS_DIFF = 0.60


def read_logits_file(path: str | Path, label: str) -> np.ndarray:
    """Read a logits JSON file and return a validated [N, 12] fp64 array."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"{label} logits file missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} logits file is not valid JSON: {path}") from exc
    logits = np.asarray(payload["logits"], dtype=np.float64)
    contract.assert_logits_12(logits)
    return logits


def compare_logits(reference: np.ndarray, candidate: np.ndarray,
                   tolerance: float) -> dict[str, Any]:
    """Return the numeric comparison report for ``candidate`` vs ``reference``."""
    reference = np.asarray(reference, dtype=np.float64)
    candidate = np.asarray(candidate, dtype=np.float64)
    if reference.shape != candidate.shape:
        raise ValueError(f"logits shape mismatch: {reference.shape} vs {candidate.shape}")
    diff = np.abs(reference - candidate)
    max_abs = float(np.max(diff))
    return {
        "max_abs_diff": max_abs,
        "mean_abs_diff": float(np.mean(diff)),
        "argmax_agreement": float(np.mean(np.argmax(reference, axis=1) == np.argmax(candidate, axis=1))),
        "tolerance": tolerance,
        "within_tolerance": max_abs <= tolerance,
    }


__all__ = ["read_logits_file", "compare_logits", "FP32_MAX_ABS_DIFF", "NPU_MAX_ABS_DIFF"]
