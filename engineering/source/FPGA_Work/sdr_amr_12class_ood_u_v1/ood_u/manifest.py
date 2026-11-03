"""M20 OOD-U threshold manifest (write-once, read-only at final blind test).

The manifest freezes every fact needed to reproduce the decision boundary: model
/ checkpoint / NPU identity, the score method, temperature, the three working
points, the calibration dataset/split SHA, sample counts, creation seed/time and
a ``final_test_accessed=false`` flag.  It is write-once (``overwrite=True`` is an
explicit escape hatch) and the reader fail-closes on any missing / malformed /
non-finite field.

A separate file-based ``FinalTestGuard`` enforces the data-isolation contract:
the blind test may be accessed exactly once, and never before the manifest is
frozen — premature or repeated access fails closed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ood_u import contract

SCHEMA_VERSION = 1

_REQUIRED_KEYS = (
    "schema_version", "model_name", "model_sha256", "checkpoint_sha256", "npu_model_sha256",
    "label_order", "input_contract", "output_numeric_type", "output_scale", "output_zero_point",
    "score_method", "score_direction", "temperature", "threshold", "working_points",
    "target_operating_point", "calibration_dataset_sha256", "calibration_split_sha256",
    "sample_count", "creation_seed", "creation_time", "final_test_accessed",
)


def _require_sha(value: Any, field: str) -> str:
    value = str(value)
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"OOD-U manifest {field!r} must be a 64-char hex SHA-256")
    return value


def _validate(manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("OOD-U manifest must be a JSON object")
    missing = [key for key in _REQUIRED_KEYS if key not in manifest]
    if missing:
        raise ValueError(f"OOD-U manifest missing required fields: {missing}")

    if int(manifest["schema_version"]) != SCHEMA_VERSION:
        raise ValueError(f"OOD-U manifest schema_version must be {SCHEMA_VERSION}")
    if str(manifest["model_name"]) != contract.MODEL_NAME:
        raise ValueError(f"OOD-U manifest model_name must be {contract.MODEL_NAME!r}")

    manifest["model_sha256"] = _require_sha(manifest["model_sha256"], "model_sha256")
    manifest["checkpoint_sha256"] = _require_sha(manifest["checkpoint_sha256"], "checkpoint_sha256")
    manifest["npu_model_sha256"] = _require_sha(manifest["npu_model_sha256"], "npu_model_sha256")
    if manifest["model_sha256"] != contract.MODEL_SHA256:
        raise ValueError("OOD-U manifest model_sha256 does not match the frozen contract")
    if manifest["npu_model_sha256"] != contract.MODEL_SHA256:
        raise ValueError("OOD-U manifest npu_model_sha256 does not match the frozen NPU model")
    if manifest["checkpoint_sha256"] != contract.CHECKPOINT_SHA256:
        raise ValueError("OOD-U manifest checkpoint_sha256 does not match the frozen checkpoint")

    contract.assert_12class_order(manifest["label_order"])

    input_contract = manifest["input_contract"]
    if not isinstance(input_contract, dict) or input_contract.get("shape") != list(contract.INPUT_SHAPE):
        raise ValueError("OOD-U manifest input_contract must carry shape [1,2,1024]")
    if str(manifest["output_numeric_type"]) != contract.OUTPUT_NUMERIC_TYPE:
        raise ValueError(f"OOD-U manifest output_numeric_type must be {contract.OUTPUT_NUMERIC_TYPE!r}")

    if str(manifest["score_method"]) not in contract.SCORE_METHODS:
        raise ValueError(f"OOD-U manifest score_method must be one of {contract.SCORE_METHODS}")
    if str(manifest["score_direction"]) != contract.DIRECTION:
        raise ValueError(f"OOD-U manifest score_direction must be {contract.DIRECTION!r}")

    temperature = float(manifest["temperature"])
    if not np.isfinite(temperature) or temperature <= 0.0:
        raise ValueError("OOD-U manifest temperature must be finite and positive")
    manifest["temperature"] = temperature

    threshold = float(manifest["threshold"])
    if not np.isfinite(threshold):
        raise ValueError("OOD-U manifest threshold is non-finite")
    manifest["threshold"] = threshold

    working = manifest["working_points"]
    if not isinstance(working, dict) or tuple(working) != contract.WORKING_POINTS:
        raise ValueError("OOD-U manifest working_points must carry id_accept_95/id_accept_99/far_ood_target")
    for name in contract.WORKING_POINTS:
        spec = working[name]
        if not isinstance(spec, dict) or "threshold" not in spec:
            raise ValueError(f"OOD-U manifest working_points[{name!r}] must carry a threshold")
        value = float(spec["threshold"])
        if not np.isfinite(value):
            raise ValueError(f"OOD-U manifest working_points[{name!r}].threshold is non-finite")
        spec["threshold"] = value

    if str(manifest["target_operating_point"]) not in contract.WORKING_POINTS:
        raise ValueError("OOD-U manifest target_operating_point must be a working point")

    manifest["calibration_dataset_sha256"] = _require_sha(
        manifest["calibration_dataset_sha256"], "calibration_dataset_sha256")
    manifest["calibration_split_sha256"] = _require_sha(
        manifest["calibration_split_sha256"], "calibration_split_sha256")

    samples = manifest["sample_count"]
    if not isinstance(samples, dict) or not {"id", "ood"} <= set(samples):
        raise ValueError("OOD-U manifest sample_count must carry id and ood counts")
    for key in ("id", "ood"):
        samples[key] = int(samples[key])
        if samples[key] < 0:
            raise ValueError(f"OOD-U manifest sample_count[{key!r}] must be non-negative")

    manifest["creation_seed"] = int(manifest["creation_seed"])
    manifest["final_test_accessed"] = bool(manifest["final_test_accessed"])
    if manifest["final_test_accessed"]:
        raise ValueError("OOD-U manifest final_test_accessed must be false at freeze time")
    return manifest


def build_ood_u_manifest(
    *,
    score_method: str,
    temperature: float,
    threshold: float,
    working_points: dict[str, dict[str, float]],
    target_operating_point: str,
    calibration_dataset_sha256: str,
    calibration_split_sha256: str,
    sample_count: dict[str, int],
    creation_seed: int,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "model_name": contract.MODEL_NAME,
        "model_sha256": contract.MODEL_SHA256,
        "checkpoint_sha256": contract.CHECKPOINT_SHA256,
        "npu_model_sha256": contract.MODEL_SHA256,
        "label_order": list(contract.LABEL_ORDER_12),
        "input_contract": {
            "shape": list(contract.INPUT_SHAPE),
            "layout": "planar_iq_c_order",
            "dtype": "fp32",
            "normalization": "rms_1.0",
        },
        "output_numeric_type": contract.OUTPUT_NUMERIC_TYPE,
        "output_scale": contract.OUTPUT_SCALE,
        "output_zero_point": contract.OUTPUT_ZERO_POINT,
        "score_method": score_method,
        "score_direction": contract.DIRECTION,
        "temperature": temperature,
        "threshold": threshold,
        "working_points": json.loads(json.dumps(working_points)),
        "target_operating_point": target_operating_point,
        "calibration_dataset_sha256": calibration_dataset_sha256,
        "calibration_split_sha256": calibration_split_sha256,
        "sample_count": dict(sample_count),
        "creation_seed": creation_seed,
        "creation_time": datetime.now(timezone.utc).isoformat(),
        "final_test_accessed": False,
    }
    return _validate(manifest)


def write_ood_u_manifest(manifest: dict[str, Any], path: str | Path, *, overwrite: bool = False) -> Path:
    manifest = _validate(dict(manifest))
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"OOD-U manifest already frozen at {path}; refusing to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_ood_u_manifest(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"OOD-U manifest not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"OOD-U manifest is not valid JSON: {path}") from exc
    return _validate(data)


def manifest_sha256(manifest: dict[str, Any]) -> str:
    canonical = json.dumps(_validate(dict(manifest)), sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class FinalTestGuard:
    """File-based single-access guard for ``ood_final_test`` (fail-closed)."""

    def __init__(self, audit_path: str | Path):
        self.audit_path = Path(audit_path)

    def assert_not_accessed(self) -> None:
        if self.audit_path.exists():
            raise RuntimeError(
                f"OOD-U final test already accessed (audit flag {self.audit_path}); "
                "re-reading the blind test set is forbidden"
            )

    def mark_accessed(self, run_id: str, manifest_sha: str) -> Path:
        self.assert_not_accessed()
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": run_id,
            "manifest_sha256": manifest_sha,
            "accessed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.audit_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.audit_path


__all__ = [
    "SCHEMA_VERSION", "build_ood_u_manifest", "write_ood_u_manifest", "read_ood_u_manifest",
    "manifest_sha256", "FinalTestGuard",
]
