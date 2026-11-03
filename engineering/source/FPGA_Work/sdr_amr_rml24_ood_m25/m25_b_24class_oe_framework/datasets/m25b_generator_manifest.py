"""Write-once generator manifest for the M25-B synthetic OOD families.

Each generated family records its provenance (modulation / source / family_code /
split_code / seed / count / per-sample SHA256) so an OE training run and an OOD
evaluation run can be reproduced bit-for-bit.  The manifest is a plain JSON object
and is written exactly once per (family, split) — re-writing with a different SHA
is refused (fail-closed), mirroring the V1.1 threshold-manifest convention.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

_SPEC_VERSION = "m25b_generator_manifest_v1"

_REQUIRED_FIELDS = (
    "spec_version", "modulation", "source", "family_code", "split_code",
    "split_name", "seed", "count", "sample_length", "sample_rate",
    "amplitude_rms", "dtype", "samples_sha256",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def samples_sha256(array: Any) -> str:
    """SHA256 over the exact bytes of the float32 planar array (row-major C order)."""
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise ImportError("numpy is required to hash samples") from exc
    arr = np.ascontiguousarray(np.asarray(array, dtype=np.float32))
    return sha256_bytes(arr.tobytes())


def build_record(*, modulation: str, source: str, family_code: int,
                 split_code: int, split_name: str, seed: int, count: int,
                 sample_length: int, sample_rate: float, amplitude_rms: float,
                 samples: Any) -> dict[str, Any]:
    """Build a full manifest record and hash the samples in one place."""
    if split_name not in ("oe_aux_train", "ood_validation", "ood_final_test"):
        raise ValueError(f"split_name must be one of oe_aux_train/ood_validation/ood_final_test, got {split_name!r}")
    record = {
        "spec_version": _SPEC_VERSION,
        "modulation": str(modulation).upper(),
        "source": str(source),
        "family_code": int(family_code),
        "split_code": int(split_code),
        "split_name": split_name,
        "seed": int(seed),
        "count": int(count),
        "sample_length": int(sample_length),
        "sample_rate": float(sample_rate),
        "amplitude_rms": float(amplitude_rms),
        "dtype": "float32",
        "samples_sha256": samples_sha256(samples),
    }
    for key in _REQUIRED_FIELDS:
        if key not in record:
            raise ValueError(f"manifest record missing required field {key!r}")
    return record


def key_of(record: dict[str, Any]) -> str:
    """Stable identity key: split_name + modulation."""
    return f"{record['split_name']}:{record['modulation']}"


def write_once(path: str, record: dict[str, Any]) -> None:
    """Write ``record`` into the JSON manifest at ``path``, refusing to overwrite a
    different SHA for the same key (fail-closed, append-new keys only)."""
    for key in _REQUIRED_FIELDS:
        if key not in record:
            raise ValueError(f"manifest record missing required field {key!r}")
    manifest: dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        if not isinstance(loaded, dict):
            raise ValueError(f"manifest at {path!r} is not a JSON object")
        manifest = loaded
        existing = manifest.get(key_of(record))
        if existing is not None:
            if existing.get("samples_sha256") != record["samples_sha256"]:
                raise RuntimeError(
                    f"refusing to overwrite manifest key {key_of(record)!r}: "
                    f"existing SHA {existing.get('samples_sha256')} != new {record['samples_sha256']}"
                )
            return  # identical record already present; idempotent
    manifest[key_of(record)] = record
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


__all__ = [
    "SPEC_VERSION", "REQUIRED_FIELDS", "sha256_bytes", "samples_sha256",
    "build_record", "key_of", "write_once",
]


# Re-export the private marker under its documented name.
SPEC_VERSION = _SPEC_VERSION
REQUIRED_FIELDS = _REQUIRED_FIELDS
