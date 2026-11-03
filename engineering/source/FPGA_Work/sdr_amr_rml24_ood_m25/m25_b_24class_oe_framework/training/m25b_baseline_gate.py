"""Baseline-frozen gate for the M25-B 24-class OE training scripts.

No OE training / calibration / final-blind run may start before the formal 24-class
baseline checkpoint is frozen and present.  Each training entrypoint calls
``require_baseline()`` first; when the baseline manifest is missing it prints
``24CLASS_BASELINE_NOT_FROZEN`` and returns a sentinel that the caller uses to
exit(0) *before* any GPU/optimizer work begins (fail-closed, no partial runs).
"""
from __future__ import annotations

import json
import os
from typing import Any

NOT_FROZEN = "24CLASS_BASELINE_NOT_FROZEN"
FROZEN = "24CLASS_BASELINE_FROZEN"

# Minimal required manifest keys (mirrors the V1.1 frozen-baseline manifest).
_REQUIRED_KEYS = ("model_sha256", "checkpoint_path", "label_order_sha256")


def _load_manifest(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        loaded = json.load(fh)
    if not isinstance(loaded, dict):
        return None
    return loaded


def baseline_status(manifest_path: str) -> tuple[str, dict[str, Any] | None]:
    manifest = _load_manifest(manifest_path)
    if manifest is None:
        return NOT_FROZEN, None
    missing = [k for k in _REQUIRED_KEYS if not manifest.get(k)]
    if missing:
        return NOT_FROZEN, manifest
    return FROZEN, manifest


def require_baseline(manifest_path: str) -> dict[str, Any] | None:
    """Return the frozen manifest, or print NOT_FROZEN and return None."""
    status, manifest = baseline_status(manifest_path)
    if status == FROZEN:
        print(FROZEN, flush=True)
        return manifest
    print(NOT_FROZEN, flush=True)
    return None


__all__ = [
    "NOT_FROZEN", "FROZEN", "REQUIRED_KEYS", "baseline_status", "require_baseline",
]

REQUIRED_KEYS = _REQUIRED_KEYS
