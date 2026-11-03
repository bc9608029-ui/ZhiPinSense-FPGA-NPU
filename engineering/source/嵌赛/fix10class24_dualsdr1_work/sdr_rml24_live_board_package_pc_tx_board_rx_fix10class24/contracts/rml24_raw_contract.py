"""M29 fix10class24-dualsdr1 Phase 2 — 24-raw-class UNMERGED deployment contract.

An *independent* deployment-layer label contract for the BF16 24-class
experimental path.  It does NOT modify the frozen 24-class contract or the
23-class merged contract (``rml23_merged_contract.py``); it *derives* from the
same frozen 24-class label order and simply does NOT merge the two AM-SSB
sub-classes:

    AM-SSB-WC (raw 17)  and  AM-SSB-SC (raw 18)  stay TWO independent classes.

The NPU emits raw 24-dim logits; this contract reports them as 24 classes
directly (argmax over 24, NO 24->23 fold).  Nothing here trains/quantizes a
model, changes the NPU input preprocessing, or the 24-dim index.

merge23(raw24) is FORBIDDEN in this mode: ``assert_merge23_forbidden`` fails
closed if a caller attempts to fold WC+SC into a 23-class result, and the
canonical contract carries ``merge23_forbidden=True`` so any accidental fold is
detectable by contract-SHA mismatch.

This module is pure-stdlib and importable under ``python -I``.
"""
from __future__ import annotations

import hashlib
import json

# --- counts ---------------------------------------------------------------
SOURCE_CLASS_COUNT = 24          # source (NPU + FP32 model) output classes
DEPLOYED_CLASS_COUNT = 24        # deployed classes == source classes (no merge)
NPU_OUTPUT_DIM = 24              # NPU raw logits dimension (unchanged)
DEPLOYMENT_MODE = "RAW24_UNMERGED"   # WC + SC stay independent; NO 24->23 fold
MODEL_MODE = "RML24-BF16-RAW"        # UI / board display identity

# --- frozen 24-class label order (verbatim copy of the frozen contract) ---
SOURCE_LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)

# The deployed label order is identical: no merge, WC at 17, SC at 18.
DEPLOYED_LABEL_ORDER_24 = SOURCE_LABEL_ORDER_24

# --- AM-SSB sub-class indices (kept SEPARATE in raw24 mode) ---------------
AMSSB_WC = 17
AMSSB_SC = 18

# --- identity (identity map: deployed index == source index) --------------
SOURCE_TO_DEPLOYED = tuple(range(SOURCE_CLASS_COUNT))

# Frozen 24-class label contract SHA (recomputed from the frozen order, the same
# convention as the v1.1 ``label_contract_sha256``).
SOURCE_LABEL_CONTRACT_SHA256 = "3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549"

# Frozen BF16 model identity (model_rml24_bf16/rml24_adamrv11_bf16.{json,raw}).
MODEL_JSON_SHA256 = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
MODEL_RAW_SHA256 = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def label_order_24_sha256() -> str:
    """Deterministic SHA256 of the raw 24-class label order."""
    return hashlib.sha256(_json_bytes(list(SOURCE_LABEL_ORDER_24))).hexdigest()


def source_label_order_sha256(order) -> str:
    """Deterministic SHA256 of an arbitrary 24-class label order (for matching)."""
    return hashlib.sha256(_json_bytes(list(order))).hexdigest()


def assert_source_order_matches(order) -> None:
    """Fail closed if ``order``'s SHA does not equal the frozen 24-class contract."""
    actual = source_label_order_sha256(order)
    if actual != SOURCE_LABEL_CONTRACT_SHA256:
        raise ValueError(
            f"source 24-class label order SHA mismatch: got {actual}, "
            f"expected {SOURCE_LABEL_CONTRACT_SHA256}"
        )


def assert_merge23_forbidden(logits24) -> None:
    """Fail closed if a caller attempts the forbidden 24->23 AM-SSB merge.

    In RAW24_UNMERGED mode the two AM-SSB sub-classes (WC=17, SC=18) are two
    independent classes; folding them into a single AM-SSB slot (the
    ``merge_logits_23`` / ``logaddexp`` fold) is FORBIDDEN here.  This guard
    rejects any 24->23 mapping table, not just a 24-dim logit vector.
    """
    raise NotImplementedError(
        "merge23(raw24) is forbidden in RAW24_UNMERGED mode: AM-SSB-WC(17) and "
        "AM-SSB-SC(18) must remain two independent classes."
    )


def canonical_contract() -> dict:
    """Canonical (sorted-key) JSON object describing the whole contract."""
    return {
        "source_class_count": SOURCE_CLASS_COUNT,
        "deployed_class_count": DEPLOYED_CLASS_COUNT,
        "npu_output_dim": NPU_OUTPUT_DIM,
        "deployment_mode": DEPLOYMENT_MODE,
        "model_mode": MODEL_MODE,
        "source_label_contract_sha256": SOURCE_LABEL_CONTRACT_SHA256,
        "model_json_sha256": MODEL_JSON_SHA256,
        "model_raw_sha256": MODEL_RAW_SHA256,
        "amssb_wc_index": AMSSB_WC,
        "amssb_sc_index": AMSSB_SC,
        "merge23_forbidden": True,
        "source_label_order_24": list(SOURCE_LABEL_ORDER_24),
        "deployed_label_order_24": list(DEPLOYED_LABEL_ORDER_24),
        "source_to_deployed": list(SOURCE_TO_DEPLOYED),
        "expert_enabled": False,
    }


def raw24_contract_sha256() -> str:
    """Deterministic SHA256 of the *full* raw24 contract, so a wrong mode / wrong
    model SHA / wrong merge flag also fails closed."""
    return hashlib.sha256(_json_bytes(canonical_contract())).hexdigest()


def assert_raw24_contract_consistent() -> None:
    """Fail closed if the derived tables are internally inconsistent."""
    assert len(SOURCE_LABEL_ORDER_24) == SOURCE_CLASS_COUNT
    assert len(DEPLOYED_LABEL_ORDER_24) == DEPLOYED_CLASS_COUNT
    assert DEPLOYED_CLASS_COUNT == SOURCE_CLASS_COUNT
    assert len(SOURCE_TO_DEPLOYED) == SOURCE_CLASS_COUNT
    # identity map: deployed index == source index everywhere (no merge)
    assert tuple(SOURCE_TO_DEPLOYED) == tuple(range(SOURCE_CLASS_COUNT))
    assert SOURCE_LABEL_ORDER_24[AMSSB_WC] == "AM-SSB-WC"
    assert SOURCE_LABEL_ORDER_24[AMSSB_SC] == "AM-SSB-SC"
    assert DEPLOYED_LABEL_ORDER_24[AMSSB_WC] == "AM-SSB-WC"
    assert DEPLOYED_LABEL_ORDER_24[AMSSB_SC] == "AM-SSB-SC"
    # label SHA must equal the frozen source contract
    assert label_order_24_sha256() == SOURCE_LABEL_CONTRACT_SHA256


if __name__ == "__main__":
    assert_raw24_contract_consistent()
    print("SOURCE_LABEL_ORDER_24:", list(SOURCE_LABEL_ORDER_24))
    print("label_order_24_sha256  =", label_order_24_sha256())
    print("raw24_contract_sha256  =", raw24_contract_sha256())
