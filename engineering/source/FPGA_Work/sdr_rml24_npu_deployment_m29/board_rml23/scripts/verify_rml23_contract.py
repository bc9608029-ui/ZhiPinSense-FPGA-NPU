#!/usr/bin/env python
"""M29 Phase F4 — board package contract verification (fail-closed).

Recomputes the deterministic SHAs from the shipped 23-class contract and checks
them against the frozen values; also re-checks the internal consistency and the
source 24-class label-order SHA.  Exits non-zero on any mismatch.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACT_DIR = os.path.join(HERE, "..", "contract")
sys.path.insert(0, CONTRACT_DIR)

from rml23_merged_contract import (  # noqa: E402
    SOURCE_LABEL_ORDER_24,
    assert_23class_contract_consistent,
    assert_source_order_matches,
    label_order_23_sha256,
    merged_contract_sha256,
)

FROZEN_LABEL_ORDER_23_SHA = "15072cd29538b08bc53f4e59237994297d71d5eb44d499413f9bb08929459c88"
FROZEN_MERGED_CONTRACT_SHA = "f9f7f3812ace1ec523c810408a31c6fc12b979d7d62900b90924cabf08bebb1e"
FROZEN_SOURCE_LABEL_SHA = "3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549"


def main() -> int:
    failures = []
    l23 = label_order_23_sha256()
    mc = merged_contract_sha256()
    print(f"  label_order_23_sha256  = {l23}")
    print(f"  merged_contract_sha256 = {mc}")
    if l23 != FROZEN_LABEL_ORDER_23_SHA:
        failures.append(f"label_order_23 SHA mismatch: {l23}")
    if mc != FROZEN_MERGED_CONTRACT_SHA:
        failures.append(f"merged_contract SHA mismatch: {mc}")
    try:
        assert_23class_contract_consistent()
        print("  [OK] contract internally consistent")
    except AssertionError as exc:
        failures.append(f"contract inconsistency: {exc}")
    try:
        assert_source_order_matches(SOURCE_LABEL_ORDER_24)
        print(f"  [OK] source 24-class label order SHA = {FROZEN_SOURCE_LABEL_SHA}")
    except ValueError as exc:
        failures.append(str(exc))

    if failures:
        print("== CONTRACT VERIFY FAILED ==")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("== CONTRACT VERIFY PASSED ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
