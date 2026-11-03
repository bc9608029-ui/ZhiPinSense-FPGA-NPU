"""Frozen OOD threshold manifest (write-once, read-only at final evaluation).

Thresholds are locked on OOD *validation* data only; the final evaluation reads
this manifest and never re-fits on test data.  This is the persistence layer for
the "threshold freeze" contract.  The manifest records everything needed to
reproduce the decision boundary: model/checkpoint identity, the score method,
temperature, the three frozen working-point thresholds, the calibration
dataset/split identity, sample counts and the calibration seed.

The manifest is write-once by default (``overwrite=True`` is an explicit escape
hatch) so a frozen threshold can never be silently replaced, and the reader
fail-closes on any missing / malformed / non-finite field.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

WORKING_POINTS = ("conservative", "balanced", "strict")
SCORE_METHODS = ("msp", "entropy", "max_logit", "energy")
DIRECTION = "higher_is_ood"

_REQUIRED_KEYS = (
    "model_sha256",
    "checkpoint_sha256",
    "score_method",
    "direction",
    "temperature",
    "thresholds",
    "calibration_dataset_sha256",
    "calibration_split_sha256",
    "target_operating_point",
    "calibration_samples",
    "creation_seed",
)


def _require_sha(value: Any, field: str) -> str:
    value = str(value)
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"threshold manifest {field!r} must be a 64-char hex SHA-256")
    return value


def _validate(manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("threshold manifest must be a JSON object")
    missing = [key for key in _REQUIRED_KEYS if key not in manifest]
    if missing:
        raise ValueError(f"threshold manifest missing required fields: {missing}")
    manifest["model_sha256"] = _require_sha(manifest["model_sha256"], "model_sha256")
    manifest["checkpoint_sha256"] = _require_sha(manifest["checkpoint_sha256"], "checkpoint_sha256")
    manifest["calibration_dataset_sha256"] = _require_sha(
        manifest["calibration_dataset_sha256"], "calibration_dataset_sha256")
    manifest["calibration_split_sha256"] = _require_sha(
        manifest["calibration_split_sha256"], "calibration_split_sha256")

    if manifest["score_method"] not in SCORE_METHODS:
        raise ValueError(f"threshold manifest score_method must be one of {SCORE_METHODS}")
    if manifest["direction"] != DIRECTION:
        raise ValueError(f"threshold manifest direction must be {DIRECTION!r}")

    temperature = float(manifest["temperature"])
    if not np.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("threshold manifest temperature must be finite and positive")
    manifest["temperature"] = temperature

    thresholds = manifest["thresholds"]
    if not isinstance(thresholds, dict) or tuple(thresholds) != WORKING_POINTS:
        raise ValueError("threshold manifest thresholds must carry conservative/balanced/strict")
    for name in WORKING_POINTS:
        spec = thresholds[name]
        if not isinstance(spec, dict) or "threshold" not in spec:
            raise ValueError(f"threshold manifest thresholds[{name!r}] must carry a threshold")
        value = float(spec["threshold"])
        if not np.isfinite(value):
            raise ValueError(f"threshold manifest thresholds[{name!r}].threshold is non-finite")
        spec["threshold"] = value
        for rate in ("id_frr", "ood_far"):
            if rate in spec:
                rate_value = float(spec[rate])
                if not np.isfinite(rate_value):
                    raise ValueError(f"threshold manifest thresholds[{name!r}].{rate} is non-finite")
                spec[rate] = rate_value

    if manifest["target_operating_point"] not in WORKING_POINTS:
        raise ValueError("threshold manifest target_operating_point must be a working point")

    samples = manifest["calibration_samples"]
    if not isinstance(samples, dict) or not {"id", "ood"} <= set(samples):
        raise ValueError("threshold manifest calibration_samples must carry id and ood counts")
    for key in ("id", "ood"):
        samples[key] = int(samples[key])
        if samples[key] < 0:
            raise ValueError(f"threshold manifest calibration_samples[{key!r}] must be non-negative")

    manifest["creation_seed"] = int(manifest["creation_seed"])
    return manifest


def build_threshold_manifest(
    *,
    model_sha256: str,
    checkpoint_sha256: str,
    score_method: str,
    thresholds: dict[str, dict[str, float]],
    calibration_dataset_sha256: str,
    calibration_split_sha256: str,
    target_operating_point: str = "balanced",
    calibration_samples: dict[str, int] | None = None,
    creation_seed: int = 2026,
    temperature: float = 1.0,
) -> dict[str, Any]:
    """Construct a validated threshold manifest.

    ``thresholds`` must be the output of ``ood.thresholds.select_thresholds``
    (three working points ``conservative``/``balanced``/``strict``).
    """
    manifest: dict[str, Any] = {
        "model_sha256": model_sha256,
        "checkpoint_sha256": checkpoint_sha256,
        "score_method": score_method,
        "direction": DIRECTION,
        "temperature": temperature,
        "thresholds": json.loads(json.dumps(thresholds)),  # deep-copy via JSON round-trip
        "calibration_dataset_sha256": calibration_dataset_sha256,
        "calibration_split_sha256": calibration_split_sha256,
        "target_operating_point": target_operating_point,
        "calibration_samples": dict(calibration_samples or {"id": 0, "ood": 0}),
        "creation_seed": creation_seed,
    }
    return _validate(manifest)


def write_threshold_manifest(manifest: dict[str, Any], path: str | Path,
                             *, overwrite: bool = False) -> Path:
    """Validate and write the manifest.  Refuses to overwrite a frozen file."""
    manifest = _validate(dict(manifest))
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"threshold manifest already frozen at {path}; refusing to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_threshold_manifest(path: str | Path) -> dict[str, Any]:
    """Read + validate a frozen manifest (fail-closed on missing/malformed)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"threshold manifest not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"threshold manifest is not valid JSON: {path}") from exc
    return _validate(data)
