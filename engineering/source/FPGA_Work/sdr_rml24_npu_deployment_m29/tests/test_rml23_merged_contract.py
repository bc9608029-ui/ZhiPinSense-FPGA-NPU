"""M29 Phase F1 — 23-class merged contract + post-processing tests.

Covers the F1-scoped offline tests: mapping uniqueness/completeness, AM-SSB
source indices, logaddexp stability, extreme logits, NaN/Inf fail-closed,
non-24-dim rejection, label-SHA mismatch rejection, raw-24 preservation,
deterministic SHAs, and the scalar/vectorized merge equivalence.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "contracts"))
sys.path.insert(0, os.path.join(ROOT, "postprocess"))

import rml23_merged as pp  # noqa: E402
from rml23_merged_contract import (  # noqa: E402
    AMSSB_DEPLOYED_INDEX,
    AMSSB_SOURCE_INDICES,
    AMSSB_SOURCE_SC,
    AMSSB_SOURCE_WC,
    DEPLOYED_CLASS_COUNT,
    DEPLOYED_LABEL_ORDER_23,
    MERGE_ALGORITHM,
    NPU_OUTPUT_DIM,
    SOURCE_CLASS_COUNT,
    SOURCE_LABEL_CONTRACT_SHA256,
    SOURCE_LABEL_ORDER_24,
    SOURCE_TO_DEPLOYED,
    assert_source_order_matches,
    canonical_contract,
    label_order_23_sha256,
    merged_contract_sha256,
    source_label_order_sha256,
)

FROZEN_LABEL_ORDER_23_SHA = "15072cd29538b08bc53f4e59237994297d71d5eb44d499413f9bb08929459c88"
FROZEN_MERGED_CONTRACT_SHA = "f9f7f3812ace1ec523c810408a31c6fc12b979d7d62900b90924cabf08bebb1e"
FROZEN_SOURCE_LABEL_SHA = "3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549"


def _sha256_json(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


# --- mapping identity ------------------------------------------------------

def test_mapping_unique_and_complete():
    assert len(SOURCE_TO_DEPLOYED) == SOURCE_CLASS_COUNT == 24
    assert set(SOURCE_TO_DEPLOYED) == set(range(DEPLOYED_CLASS_COUNT))
    counts = {}
    for d in SOURCE_TO_DEPLOYED:
        counts[d] = counts.get(d, 0) + 1
    assert counts[AMSSB_DEPLOYED_INDEX] == 2          # WC + SC -> one slot
    assert all(v == 1 for k, v in counts.items() if k != AMSSB_DEPLOYED_INDEX)


def test_amssb_source_indices():
    assert AMSSB_SOURCE_INDICES == (17, 18)
    assert SOURCE_LABEL_ORDER_24[AMSSB_SOURCE_WC] == "AM-SSB-WC"
    assert SOURCE_LABEL_ORDER_24[AMSSB_SOURCE_SC] == "AM-SSB-SC"
    assert DEPLOYED_LABEL_ORDER_23[AMSSB_DEPLOYED_INDEX] == "AM-SSB"
    assert MERGE_ALGORITHM == "logaddexp"


def test_22_non_amssb_order_preserved():
    assert list(DEPLOYED_LABEL_ORDER_23[:17]) == list(SOURCE_LABEL_ORDER_24[:17])
    assert list(DEPLOYED_LABEL_ORDER_23[18:]) == list(SOURCE_LABEL_ORDER_24[19:])


# --- deterministic SHAs ----------------------------------------------------

def test_label_order_23_sha256_deterministic():
    assert label_order_23_sha256() == FROZEN_LABEL_ORDER_23_SHA
    assert _sha256_json(list(DEPLOYED_LABEL_ORDER_23)) == FROZEN_LABEL_ORDER_23_SHA


def test_merged_contract_sha256_deterministic():
    assert merged_contract_sha256() == FROZEN_MERGED_CONTRACT_SHA


def test_source_label_sha_matches_frozen():
    assert SOURCE_LABEL_CONTRACT_SHA256 == FROZEN_SOURCE_LABEL_SHA
    assert _sha256_json(list(SOURCE_LABEL_ORDER_24)) == FROZEN_SOURCE_LABEL_SHA


def test_contract_json_matches_module():
    p = os.path.join(ROOT, "contracts", "rml23_merged_contract.json")
    with open(p, "r", encoding="utf-8") as f:
        doc = json.load(f)
    assert doc["label_order_23_sha256"] == FROZEN_LABEL_ORDER_23_SHA
    assert doc["merged_contract_sha256"] == FROZEN_MERGED_CONTRACT_SHA
    assert doc["deployed_label_order_23"] == list(DEPLOYED_LABEL_ORDER_23)
    assert doc["amssb_source_indices"] == [17, 18]
    assert doc["npu_output_dim"] == 24
    assert doc["deployed_class_count"] == 23
    assert doc["expert_enabled"] is False


# --- label-SHA mismatch rejection -----------------------------------------

def test_label_sha_mismatch_rejected():
    assert_source_order_matches(SOURCE_LABEL_ORDER_24)  # exact -> ok
    wrong = list(SOURCE_LABEL_ORDER_24)
    wrong[0], wrong[1] = wrong[1], wrong[0]             # swap two classes
    with pytest.raises(ValueError, match="SHA mismatch"):
        assert_source_order_matches(wrong)
    with pytest.raises(ValueError):
        assert_source_order_matches(list(SOURCE_LABEL_ORDER_24) + ["EXTRA"])


# --- logaddexp math --------------------------------------------------------

def test_logaddexp_matches_numpy():
    xs = [-1000.0, -100.0, -1.0, 0.0, 1.0, 2.5, 100.0, 1000.0]
    for a in xs:
        for b in xs:
            assert math.isclose(pp.logaddexp(a, b), np.logaddexp(a, b), rel_tol=1e-12)


def test_logaddexp_stability_extremes():
    # no overflow on large equal args
    assert math.isclose(pp.logaddexp(1000.0, 1000.0), 1000.0 + math.log(2.0), rel_tol=1e-12)
    # no underflow to -inf on large negative args
    assert pp.logaddexp(-1000.0, -1000.0) > float("-inf")
    assert math.isclose(pp.logaddexp(-1000.0, -1000.0), -1000.0 + math.log(2.0), rel_tol=1e-12)
    # infinities
    assert pp.logaddexp(float("-inf"), 3.0) == 3.0
    assert pp.logaddexp(3.0, float("-inf")) == 3.0
    assert pp.logaddexp(float("-inf"), float("-inf")) == float("-inf")
    assert pp.logaddexp(float("inf"), 3.0) == float("inf")
    # domination: one argument dwarfs the other
    assert pp.logaddexp(1000.0, 0.0) == 1000.0


# --- merge semantics -------------------------------------------------------

def test_merge_math_correct():
    logits = [float(i) for i in range(24)]
    merged = pp.merge_logits_24_to_23(logits)
    assert len(merged) == 23
    assert merged[:17] == [float(i) for i in range(17)]
    assert merged[18:] == [float(i) for i in range(19, 24)]
    assert merged[17] == pytest.approx(np.logaddexp(17.0, 18.0))


def test_merge_preserves_raw24_and_input_unchanged():
    logits = [float(i) for i in range(24)]
    snapshot = list(logits)
    merged = pp.merge_logits_24_to_23(logits)
    assert logits == snapshot                       # input not mutated
    # non-merged slots are the raw values, not derived
    assert merged[5] == 5.0
    assert merged[22] == 23.0


def test_merge_when_wc_dominates():
    logits = [0.0] * 24
    logits[17], logits[18] = 5.0, -100.0
    assert pp.merge_logits_24_to_23(logits)[17] == pytest.approx(5.0)


def test_merge_when_sc_dominates():
    logits = [0.0] * 24
    logits[17], logits[18] = -100.0, 5.0
    assert pp.merge_logits_24_to_23(logits)[17] == pytest.approx(5.0)


def test_extreme_finite_logits_stable():
    logits = [0.0] * 24
    logits[17], logits[18] = 1e6, 1e6
    merged = pp.merge_logits_24_to_23(logits)
    assert math.isclose(merged[17], 1e6 + math.log(2.0), rel_tol=1e-12)
    assert math.isfinite(merged[17])


# --- fail-closed rejections ------------------------------------------------

def test_nan_rejected():
    logits = [0.0] * 24
    logits[3] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        pp.merge_logits_24_to_23(logits)


@pytest.mark.parametrize("bad", [float("inf"), float("-inf")])
def test_inf_rejected(bad):
    logits = [0.0] * 24
    logits[10] = bad
    with pytest.raises(ValueError, match="non-finite"):
        pp.merge_logits_24_to_23(logits)


@pytest.mark.parametrize("n", [0, 1, 22, 23, 25, 100])
def test_non_24_dim_rejected(n):
    with pytest.raises(ValueError, match="24-dim"):
        pp.merge_logits_24_to_23([0.0] * n)


def test_vectorized_rejects_nonfinite():
    a = np.zeros((4, 24), dtype=np.float64)
    a[1, 3] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        pp.merge_many_24_to_23(a)


# --- argmax / prediction ---------------------------------------------------

def test_predict_23_argmax_unmerged_class():
    logits = [0.0] * 24
    logits[5] = 9.0
    idx, label = pp.predict_23(logits)
    assert idx == 5
    assert label == "8PSK"


def test_predict_23_argmax_amssb_wc():
    logits = [0.0] * 24
    logits[17] = 9.0
    idx, label = pp.predict_23(logits)
    assert idx == 17
    assert label == "AM-SSB"


def test_predict_23_argmax_amssb_sc():
    logits = [0.0] * 24
    logits[18] = 9.0
    idx, label = pp.predict_23(logits)
    assert idx == 17
    assert label == "AM-SSB"


def test_predict_23_full_record():
    logits = [0.0] * 24
    logits[18] = 9.0
    rec = pp.predict_23_full(logits)
    assert rec["raw_24_top1"] == 18
    assert rec["merged_23_top1"] == 17
    assert rec["merged_23_label"] == "AM-SSB"
    assert rec["deployment_mode"] == "AMSSB_MERGED"
    assert rec["expert_enabled"] is False
    assert rec["expert_result"] == "NOT_RUN"


# --- scalar / vectorized equivalence ---------------------------------------

def test_vectorized_matches_scalar():
    rng = np.random.default_rng(0)
    a = rng.normal(size=(50, 24))
    vec = pp.merge_many_24_to_23(a)
    for i in range(50):
        row = pp.merge_logits_24_to_23(a[i].tolist())
        assert np.allclose(vec[i], row, atol=1e-12)


def test_contract_is_consistent():
    # the module-level self-check must pass
    import rml23_merged_contract as c
    c.assert_23class_contract_consistent()


def test_canonical_contract_has_required_fields():
    doc = canonical_contract()
    for key in ("source_class_count", "deployed_class_count", "npu_output_dim",
                "deployment_mode", "amssb_source_indices", "merge_algorithm",
                "source_label_contract_sha256", "expert_enabled"):
        assert key in doc
    assert doc["source_class_count"] == 24
    assert doc["deployed_class_count"] == 23
    assert doc["npu_output_dim"] == 24
    assert doc["deployment_mode"] == "AMSSB_MERGED"
