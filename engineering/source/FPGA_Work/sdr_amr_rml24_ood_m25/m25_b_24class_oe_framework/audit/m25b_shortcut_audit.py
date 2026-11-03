"""Generator-shortcut audit for the M25-B OE data path.

Forbids the one real leakage channel a self-contained OOD generator could have:
drawing OOD samples from the ID HDF5 generator path (i.e. borrowing ID examples
and re-labelling them as outliers).  Any OOD provenance record that traces back to
the ID generator is flagged with ``OOD_PROTOCOL_INVALID reason=generator_shortcut``.
"""
from __future__ import annotations

from typing import Any, Iterable

from contracts.m25b_oe_data_protocol import OOD_PROTOCOL_INVALID

_SHORTCUT_CLEAN = "M25B_SHORTCUT_CLEAN"
_SHORTCUT_VIOLATION = "M25B_SHORTCUT_VIOLATION"

# Provenance fields whose presence indicates the sample came from the ID path.
_ID_GENERATOR_MARKERS = ("id_hdf5", "id_label", "id_index", "id_dataset")


def audit_shortcut(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Flag any record that references the ID generator / ID label space."""
    violations: list[dict[str, Any]] = []
    for r in records:
        record = dict(r)
        hits = [m for m in _ID_GENERATOR_MARKERS if m in record and record.get(m)]
        # OE modulation must not collide with the ID label space (defence in depth).
        id_label = record.get("id_label")
        if hits or id_label is not None:
            violations.append({
                "status": OOD_PROTOCOL_INVALID,
                "reason": "generator_shortcut",
                "markers": hits,
                "record": record,
            })
    status = _SHORTCUT_VIOLATION if violations else _SHORTCUT_CLEAN
    return {
        "status": status,
        "num_records": len(list(records)) if not isinstance(records, list) else len(records),
        "num_violations": len(violations),
        "violations": violations,
    }


def assert_no_shortcut(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    result = audit_shortcut(records)
    if result["status"] != _SHORTCUT_CLEAN:
        raise RuntimeError(
            f"shortcut audit failed: {result['num_violations']} violation(s): "
            f"{result['violations']}"
        )
    return result


__all__ = [
    "OOD_PROTOCOL_INVALID", "SHORTCUT_CLEAN", "SHORTCUT_VIOLATION",
    "audit_shortcut", "assert_no_shortcut",
]

SHORTCUT_CLEAN = _SHORTCUT_CLEAN
SHORTCUT_VIOLATION = _SHORTCUT_VIOLATION
