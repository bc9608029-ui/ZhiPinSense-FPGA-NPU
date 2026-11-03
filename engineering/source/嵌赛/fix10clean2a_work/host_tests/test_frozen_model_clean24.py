"""Host test 4/4 — the frozen model evaluation.

Covers §12 items: 16 (checkpoint SHA), 17 (inference determinism), 18 (scored == n),
6/8 (24->23 merge, AM-SSB fold), 20 (accuracy gate requires full count, not scored>0).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

import evaluate_frozen_model_on_clean24 as ev
from rml23_merged import merge_many_24_to_23
from rml23_merged_contract import SOURCE_TO_DEPLOYED

CHECKPOINT = Path(ev.CHECKPOINT)
RESULTS = Path(ev.RESULTS_DIR)


def _accepts(raw24: dict, dep23: dict, n_scored: int, n_excluded: int, nan_inf: int) -> bool:
    """The §11.1 acceptance gate.  Requires scored == 12000, NOT merely scored > 0."""
    return (
        raw24["overall"] >= 0.95
        and raw24["macro"] >= 0.95
        and dep23["overall"] >= 0.95
        and dep23["macro"] >= 0.95
        and min(dep23["per_class_recall"].values()) >= 0.90
        and n_scored == 12000
        and n_excluded == 0
        and nan_inf == 0
    )


def test_checkpoint_sha_correct():
    # §12 item 16: the frozen checkpoint must hash-match before any inference.
    sha = hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest()
    assert sha == ev.EXPECTED_CHECKPOINT_SHA


def test_inference_deterministic():
    # §12 item 17: two inference passes over the same clean set are bit-identical.
    model, _ = ev._load_model()
    x_in, Y, seeds = ev._load_dataset("smoke96")
    a = ev._predict(model, x_in)
    b = ev._predict(model, x_in)
    assert np.array_equal(a, b)


def test_scored_equals_total_smoke96():
    # §12 item 18: scored == n (no silent exclusion), balanced per class.
    model, _ = ev._load_model()
    x_in, Y, seeds = ev._load_dataset("smoke96")
    logits = ev._predict(model, x_in)
    assert logits.shape[0] == 96
    assert int((Y == 0).sum()) == 4 and int((Y == 23).sum()) == 4
    raw = ev._raw24_metrics(logits, Y)
    assert sum(raw["per_class_count"].values()) == 96
    assert all(v == 4 for v in raw["per_class_count"].values())


def test_24_to_23_merge_folds_am_ssb():
    # §12 items 6/8: the deployed merge folds AM-SSB-WC(17)+SC(18) into class 17.
    logits = np.zeros((2, 24), dtype=np.float64)
    logits[0, 17] = 10.0      # WC strongly fired
    logits[1, 18] = 10.0      # SC strongly fired
    merged = merge_many_24_to_23(logits)
    assert merged.shape == (2, 23)
    assert list(merged.argmax(axis=1)) == [17, 17]


def test_formal_acceptance_requires_full_count():
    # §12 item 20 + §11.1: the CLEAN_IQ_MODEL_COMPATIBLE_PASS gate must demand the
    # full 12000 scored samples — a scored>0 gate must NOT be enough.
    d = json.loads((RESULTS / "CLEAN2A_PHASE5_MODEL_EVAL_formal12000.json").read_text(encoding="utf-8"))
    assert d["n_samples"] == 12000
    assert d["n_excluded"] == 0
    assert d["nan_inf"] == 0
    # full 12000 -> PASS
    assert _accepts(d["raw24"], d["deployed23"], 12000, 0, 0)
    # identical metrics but scored>0 (e.g. 1 sample) -> REJECTED by this gate
    assert not _accepts(d["raw24"], d["deployed23"], 1, 0, 0)
    # a single dropped sample (scored=11999) is also REJECTED (full-count, not "almost")
    assert not _accepts(d["raw24"], d["deployed23"], 11999, 0, 0)
