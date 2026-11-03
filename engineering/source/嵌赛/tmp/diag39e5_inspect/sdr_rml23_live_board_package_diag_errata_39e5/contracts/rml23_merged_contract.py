"""M29 Phase F1 — 23-class AM-SSB merged deployment contract.

An *independent* deployment-layer label contract.  It does NOT modify the frozen
24-class contract (``_frozen/contracts/rml24_contract.py``); it *derives* from it
by merging the two AM-SSB sub-classes into one deployed class:

    AM-SSB-SC + AM-SSB-WC  ->  AM-SSB          (deployment layer only)

The NPU still emits raw 24-dim logits; the merge happens in software
post-processing, which then emits 23 classes.  Nothing here trains an expert
model, and nothing here changes the NPU input preprocessing or the 24-dim index.

Merge semantics (audited, not a deletion, not a mean):
    merged_AMSSB = logaddexp(logit_AM_SSB_SC, logit_AM_SSB_WC)
                 = log( exp(logit_SC) + exp(logit_WC) )

This is the log-domain sum of two mutually-exclusive classes' probability mass —
exactly "P(AM-SSB) = P(SC) + P(WC)" carried into log space.  It is monotonic and
symmetric in its two arguments, and it preserves the full SC+WC signal.  A naive
argmax-over-24 with 17/18 folded is NOT sufficient for F2's merged-margin /
confusion metrics, so the full merged logit is computed here.

This module is pure-stdlib and importable under ``python -I``.
"""
from __future__ import annotations

import hashlib
import json

# --- counts ---------------------------------------------------------------
SOURCE_CLASS_COUNT = 24          # source (NPU + FP32 model) output classes
DEPLOYED_CLASS_COUNT = 23        # classes the UI / board reports after merge
NPU_OUTPUT_DIM = 24              # NPU raw logits dimension (unchanged)
DEPLOYMENT_MODE = "AMSSB_MERGED"  # SC + WC -> AM-SSB at deployment layer

# --- frozen 24-class label order (verbatim copy of the frozen contract) ---
SOURCE_LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)

# --- merged 23-class label order ------------------------------------------
# The 22 non-AM-SSB classes keep their original order; the two AM-SSB classes
# collapse to a single "AM-SSB" at the position of the *first* (WC, index 17).
DEPLOYED_LABEL_ORDER_23 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB", "AM-DSB-WC", "AM-DSB-SC", "FM", "GMSK",
    "OQPSK",
)

# --- merge indices (24-class space) ---------------------------------------
AMSSB_SOURCE_INDICES = (17, 18)  # (AM-SSB-WC, AM-SSB-SC)
AMSSB_SOURCE_WC = 17
AMSSB_SOURCE_SC = 18
AMSSB_DEPLOYED_INDEX = 17        # position of "AM-SSB" in the 23-class order
MERGE_ALGORITHM = "logaddexp"    # merged = log(exp(logit_SC) + exp(logit_WC))

# --- mapping tables -------------------------------------------------------
# SOURCE_TO_DEPLOYED[i] = 23-class slot that 24-class index i lands in.
# Indices 17 (WC) and 18 (SC) both land in 17 (AM-SSB); 19..23 shift down by 1.
SOURCE_TO_DEPLOYED = (
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
    17, 17, 18, 19, 20, 21, 22,
)

# The identical table read as a label map (24-class label -> 23-class label).
LABEL_MAP_24_TO_23 = SOURCE_TO_DEPLOYED

# Frozen 24-class label contract SHA (recomputed from the frozen order, the same
# convention as the v1.1 ``label_contract_sha256``).
SOURCE_LABEL_CONTRACT_SHA256 = "3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549"


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def label_order_23_sha256() -> str:
    """Deterministic SHA256 of the deployed 23-class label order."""
    return hashlib.sha256(_json_bytes(list(DEPLOYED_LABEL_ORDER_23))).hexdigest()


def source_label_order_sha256(order) -> str:
    """Deterministic SHA256 of an arbitrary 24-class label order (for matching)."""
    return hashlib.sha256(_json_bytes(list(order))).hexdigest()


def assert_source_order_matches(order) -> None:
    """Fail closed if ``order``'s SHA does not equal the frozen 24-class contract.

    This is the label-SHA mismatch rejection used before any 24->23 mapping: the
    NPU model's label order (or a candidate's reported label order) must hash to
    the frozen source contract before its logits may be merged.
    """
    actual = source_label_order_sha256(order)
    if actual != SOURCE_LABEL_CONTRACT_SHA256:
        raise ValueError(
            f"source 24-class label order SHA mismatch: got {actual}, "
            f"expected {SOURCE_LABEL_CONTRACT_SHA256}"
        )


def merged_contract_sha256() -> str:
    """Deterministic SHA256 of the *full* merged contract (labels + indices +
    mode + source SHA), so a wrong merge index or wrong mode also fails closed."""
    return hashlib.sha256(_json_bytes(canonical_contract())).hexdigest()


def canonical_contract() -> dict:
    """Canonical (sorted-key) JSON object describing the whole contract."""
    return {
        "source_class_count": SOURCE_CLASS_COUNT,
        "deployed_class_count": DEPLOYED_CLASS_COUNT,
        "npu_output_dim": NPU_OUTPUT_DIM,
        "deployment_mode": DEPLOYMENT_MODE,
        "source_label_contract_sha256": SOURCE_LABEL_CONTRACT_SHA256,
        "amssb_source_indices": list(AMSSB_SOURCE_INDICES),
        "amssb_deployed_index": AMSSB_DEPLOYED_INDEX,
        "merge_algorithm": MERGE_ALGORITHM,
        "source_label_order_24": list(SOURCE_LABEL_ORDER_24),
        "deployed_label_order_23": list(DEPLOYED_LABEL_ORDER_23),
        "source_to_deployed": list(SOURCE_TO_DEPLOYED),
        "expert_enabled": False,
    }


def assert_23class_contract_consistent() -> None:
    """Fail closed if the derived tables are internally inconsistent."""
    assert len(SOURCE_LABEL_ORDER_24) == SOURCE_CLASS_COUNT
    assert len(DEPLOYED_LABEL_ORDER_23) == DEPLOYED_CLASS_COUNT
    assert len(SOURCE_TO_DEPLOYED) == SOURCE_CLASS_COUNT
    assert SOURCE_LABEL_ORDER_24[AMSSB_SOURCE_WC] == "AM-SSB-WC"
    assert SOURCE_LABEL_ORDER_24[AMSSB_SOURCE_SC] == "AM-SSB-SC"
    assert DEPLOYED_LABEL_ORDER_23[AMSSB_DEPLOYED_INDEX] == "AM-SSB"
    assert SOURCE_TO_DEPLOYED[AMSSB_SOURCE_WC] == AMSSB_DEPLOYED_INDEX
    assert SOURCE_TO_DEPLOYED[AMSSB_SOURCE_SC] == AMSSB_DEPLOYED_INDEX
    # the 22 non-AM-SSB classes are exactly the merged order minus "AM-SSB"
    expected_rest = list(DEPLOYED_LABEL_ORDER_23[:17]) + list(DEPLOYED_LABEL_ORDER_23[18:])
    source_rest = (list(SOURCE_LABEL_ORDER_24[:17])
                   + list(SOURCE_LABEL_ORDER_24[19:]))
    assert expected_rest == source_rest, "non-AM-SSB class order must be preserved"
    # every deployed slot 0..22 is reachable; the merged slot (17) is reached
    # exactly twice (WC + SC), every other slot exactly once.
    from collections import Counter
    counts = Counter(SOURCE_TO_DEPLOYED)
    assert set(SOURCE_TO_DEPLOYED) == set(range(DEPLOYED_CLASS_COUNT))
    assert counts[AMSSB_DEPLOYED_INDEX] == 2, "AM-SSB slot must absorb WC + SC"
    assert all(counts[d] == 1 for d in range(DEPLOYED_CLASS_COUNT)
               if d != AMSSB_DEPLOYED_INDEX), "non-AM-SSB slots must be 1:1"


if __name__ == "__main__":
    assert_23class_contract_consistent()
    print("DEPLOYED_LABEL_ORDER_23:", list(DEPLOYED_LABEL_ORDER_23))
    print("label_order_23_sha256   =", label_order_23_sha256())
    print("merged_contract_sha256  =", merged_contract_sha256())
