"""Three-way isolation audit for the M25-B OE data splits.

The OOD generator draws each (family, split) from its own SeedSequence stream, so
the *same* modulation legitimately appears in all three splits with *different*
samples.  Isolation is therefore about:

  1. split_code <-> split_name mapping consistency (0/1/2 <-> oe_aux/validation/final)
  2. sample non-leakage: when records carry ``samples_sha256``, the same sample
     must never appear in more than one split (byte-identical leakage)
  3. per-split, per-modulation counts (reported, not enforced)

A collision is a violation; a modulation appearing in multiple splits is normal.
"""
from __future__ import annotations

from typing import Any, Iterable

from contracts.m25b_oe_data_protocol import OE_SPLITS, OE_SOURCES

_SPLIT_BY_CODE = {0: "oe_aux_train", 1: "ood_validation", 2: "ood_final_test"}

_ISOLATION_OK = "M25B_ISOLATION_OK"
_ISOLATION_VIOLATION = "M25B_ISOLATION_VIOLATION"


def _norm(record: dict[str, Any]) -> dict[str, Any]:
    split_code = int(record.get("split_code", -1))
    split_name = record.get("split_name") or _SPLIT_BY_CODE.get(split_code)
    return {
        "modulation": str(record.get("modulation", "")).upper(),
        "source": str(record.get("source", "")),
        "family_code": int(record.get("family_code", -1)),
        "split_code": split_code,
        "split_name": split_name,
        "samples_sha256": record.get("samples_sha256"),
    }


def audit_isolation(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    recs = [_norm(r) for r in records]
    counts: dict[str, dict[str, int]] = {s: {} for s in OE_SPLITS}
    violations: list[dict[str, Any]] = []
    # samples_sha256 -> split_name (for non-leakage check across splits)
    sample_owner: dict[str, str] = {}

    for r in recs:
        split = r["split_name"]
        if split not in OE_SPLITS:
            violations.append({"reason": "bad_split", "record": r})
            continue
        if r["source"] not in OE_SOURCES and r["source"] != "ambiguous":
            violations.append({"reason": "bad_source", "record": r})
            continue
        # split_code <-> split_name consistency
        if r["split_code"] not in _SPLIT_BY_CODE:
            violations.append({"reason": "bad_split_code", "record": r})
            continue
        if _SPLIT_BY_CODE[r["split_code"]] != split:
            violations.append({
                "reason": "split_mapping_mismatch",
                "split_code": r["split_code"],
                "split_name": split,
                "expected": _SPLIT_BY_CODE[r["split_code"]],
            })
            continue
        # sample non-leakage across splits
        sha = r["samples_sha256"]
        if sha:
            prev = sample_owner.get(sha)
            if prev is not None and prev != split:
                violations.append({
                    "reason": "sample_leakage",
                    "samples_sha256": sha,
                    "first_split": prev,
                    "second_split": split,
                })
            else:
                sample_owner[sha] = split
        counts[split][r["modulation"]] = counts[split].get(r["modulation"], 0) + 1

    return {
        "status": _ISOLATION_VIOLATION if violations else _ISOLATION_OK,
        "num_records": len(recs),
        "num_violations": len(violations),
        "counts_by_split": counts,
        "violations": violations,
    }


def assert_isolated(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    result = audit_isolation(records)
    if result["status"] != _ISOLATION_OK:
        raise RuntimeError(
            f"isolation audit failed: {result['num_violations']} violation(s): "
            f"{result['violations']}"
        )
    return result


__all__ = [
    "OE_SPLITS", "OE_SOURCES", "ISOLATION_OK", "ISOLATION_VIOLATION",
    "audit_isolation", "assert_isolated",
]

ISOLATION_OK = _ISOLATION_OK
ISOLATION_VIOLATION = _ISOLATION_VIOLATION
