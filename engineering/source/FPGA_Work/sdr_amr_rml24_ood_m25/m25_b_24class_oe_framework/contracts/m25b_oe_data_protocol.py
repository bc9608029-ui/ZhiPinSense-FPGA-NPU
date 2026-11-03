"""Outlier-Exposure data protocol for M25-B.

OE samples are NOT a 25th class.  They are auxiliary inputs used only to shape
raw logits via the Energy OE loss and to calibrate/evaluate OOD thresholds.  Each
OE sample carries a ``source`` (near/far) and a ``family_code``; it is NEVER
merged into the 24-class ID label space.
"""
from __future__ import annotations

from typing import Any

# OE sources and the frozen split names.
OE_SOURCES = ("near", "far")
OE_SPLITS = ("oe_aux_train", "ood_validation", "ood_final_test")

# OE auxiliary training may only draw from oe_aux_train; the OOD *evaluation*
# families may only draw from ood_validation / ood_final_test.
OE_AUX_SPLIT = "oe_aux_train"
OOD_EVAL_SPLITS = ("ood_validation", "ood_final_test")

# Shortcut-audit marker emitted when an OOD stream is traced back to the ID HDF5
# generator path (which is forbidden).
OOD_PROTOCOL_INVALID = "OOD_PROTOCOL_INVALID"

# Canonical OE sample record (metadata, not a training label).
OE_SAMPLE_KEYS = (
    "source", "family_code", "modulation", "split_code", "seed",
    "sample_index", "sample_length", "sample_rate", "amplitude_rms",
    "ood_synthesis",
)


def assert_oe_not_id_label(modulation: str, id_labels: set[str]) -> None:
    """Refuse to treat an OE modulation as a member of the ID label space."""
    name = str(modulation).upper()
    if name in {str(x).upper() for x in id_labels}:
        raise ValueError(
            f"OE modulation {name!r} collides with the ID label space; "
            "OE samples are auxiliary inputs, never a 25th class"
        )


def oe_sample_record(*, source: str, family_code: int, modulation: str,
                     split_code: int, seed: int, sample_index: int,
                     sample_length: int, sample_rate: float, amplitude_rms: float,
                     ood_synthesis: str = "synthetic") -> dict[str, Any]:
    if source not in OE_SOURCES:
        raise ValueError(f"OE source must be one of {OE_SOURCES}, got {source!r}")
    if split_code not in (0, 1, 2):
        raise ValueError("split_code must be one of 0(oe_aux)/1(validation)/2(final)")
    return {
        "source": source,
        "family_code": int(family_code),
        "modulation": str(modulation).upper(),
        "split_code": int(split_code),
        "seed": int(seed),
        "sample_index": int(sample_index),
        "sample_length": int(sample_length),
        "sample_rate": float(sample_rate),
        "amplitude_rms": float(amplitude_rms),
        "ood_synthesis": str(ood_synthesis),
    }
