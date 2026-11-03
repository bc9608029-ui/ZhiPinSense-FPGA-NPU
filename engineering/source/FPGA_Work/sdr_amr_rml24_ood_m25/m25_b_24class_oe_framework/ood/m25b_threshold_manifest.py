"""Write-once threshold manifest for the M25-B 24-class OOD thresholds.

Mirrors the V1.1 threshold-manifest convention: a JSON object with the required
fields, written exactly once; re-writing a threshold for the same frozen key is
refused (fail-closed) so a locked calibration cannot be silently re-calibrated.
"""
from __future__ import annotations

import json
import os
from typing import Any

_SPEC_VERSION = "m25b_threshold_manifest_v1"

_REQUIRED_KEYS = (
    "spec_version", "model_sha256", "score_name", "split_name",
    "id_accept_99", "id_accept_95", "far_ood", "id_accept_rate_at_99",
    "far_reject_rate_at_99", "num_id", "num_far_ood", "created_utc",
)


def build_threshold_record(*, model_sha256: str, score_name: str, split_name: str,
                           id_accept_99: float, id_accept_95: float, far_ood: float,
                           id_accept_rate_at_99: float, far_reject_rate_at_99: float,
                           num_id: int, num_far_ood: int,
                           created_utc: str) -> dict[str, Any]:
    if split_name not in ("ood_validation", "ood_final_test"):
        raise ValueError("thresholds may only be locked on ood_validation / ood_final_test")
    record = {
        "spec_version": _SPEC_VERSION,
        "model_sha256": str(model_sha256),
        "score_name": str(score_name),
        "split_name": split_name,
        "id_accept_99": float(id_accept_99),
        "id_accept_95": float(id_accept_95),
        "far_ood": float(far_ood),
        "id_accept_rate_at_99": float(id_accept_rate_at_99),
        "far_reject_rate_at_99": float(far_reject_rate_at_99),
        "num_id": int(num_id),
        "num_far_ood": int(num_far_ood),
        "created_utc": str(created_utc),
    }
    for key in _REQUIRED_KEYS:
        if key not in record:
            raise ValueError(f"threshold record missing required key {key!r}")
    return record


def threshold_key(record: dict[str, Any]) -> str:
    return f"{record['model_sha256']}:{record['score_name']}:{record['split_name']}"


def write_once(path: str, record: dict[str, Any]) -> None:
    for key in _REQUIRED_KEYS:
        if key not in record:
            raise ValueError(f"threshold record missing required key {key!r}")
    manifest: dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        if not isinstance(loaded, dict):
            raise ValueError(f"threshold manifest at {path!r} is not a JSON object")
        manifest = loaded
        key = threshold_key(record)
        if key in manifest:
            existing = manifest[key]
            existing_vals = {k: existing.get(k) for k in ("id_accept_99", "id_accept_95", "far_ood")}
            new_vals = {k: record.get(k) for k in ("id_accept_99", "id_accept_95", "far_ood")}
            if existing_vals != new_vals:
                raise RuntimeError(
                    f"refusing to overwrite threshold key {key!r}: "
                    f"existing {existing_vals} != new {new_vals}"
                )
            return  # identical; idempotent
    manifest[threshold_key(record)] = record
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


def load_manifest(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"threshold manifest not found: {path!r}")
    with open(path, "r", encoding="utf-8") as fh:
        loaded = json.load(fh)
    if not isinstance(loaded, dict):
        raise ValueError(f"threshold manifest at {path!r} is not a JSON object")
    return loaded


__all__ = [
    "SPEC_VERSION", "REQUIRED_KEYS", "build_threshold_record", "threshold_key",
    "write_once", "load_manifest",
]

SPEC_VERSION = _SPEC_VERSION
REQUIRED_KEYS = _REQUIRED_KEYS
