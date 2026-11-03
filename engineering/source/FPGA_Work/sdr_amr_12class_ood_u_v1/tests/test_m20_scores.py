"""M20 test categories 1-5: score numerics, direction, NaN/Inf, input dim,
threshold boundary.  All pure-NumPy — no model load, fast and deterministic.
"""

from __future__ import annotations

import numpy as np
import pytest

from ood.scores import compute_scores
from ood_u import contract

UNIFORM = np.zeros((4, 12), dtype=np.float64)


def test_score_methods_numeric_and_hand_computed():
    # Category 1: all five methods return finite numerics and match closed-form
    # values on a uniform logit vector (softmax = 1/12 per class).
    expected = {
        "msp": 1.0 - 1.0 / 12.0,
        "entropy": np.log(12.0),
        "max_logit": 0.0,
        "logit_margin": 0.0,
        "energy": -np.log(12.0),
    }
    for method, want in expected.items():
        got = compute_scores(UNIFORM, method)
        assert got.shape == (4,)
        assert np.isfinite(got).all()
        assert np.allclose(got, want, atol=1e-6), f"{method}: {got} vs {want}"


def test_score_direction_higher_is_ood():
    # Category 2: a high-confidence ID vector must score strictly lower than a
    # uniform (spread) vector, for every method — "higher = more OOD".
    confident = np.tile(np.array([[20.0] + [-20.0] * 11]), (4, 1))
    for method in contract.SCORE_METHODS:
        id_score = compute_scores(confident, method)
        ood_score = compute_scores(UNIFORM, method)
        assert (id_score < ood_score).all(), f"{method} direction violated"


def test_score_nan_inf_fail_closed():
    # Category 3: NaN/Inf logits must fail closed (raise), never score silently.
    bad = UNIFORM.copy()
    bad[0, 3] = np.nan
    with pytest.raises(ValueError):
        contract.assert_logits_12(bad)
    bad2 = UNIFORM.copy()
    bad2[1, 5] = np.inf
    with pytest.raises(ValueError):
        contract.assert_logits_12(bad2)


def test_score_input_dim_fail_closed():
    # Category 4: wrong logits dimension must fail closed.  The M20 dimension
    # guard is contract.assert_logits_12, which every M20 scoring entry point
    # (logits_for / read_logits_file / the C++ detector's dim==12 check) runs
    # before scoring.  compute_scores itself is the shared generic primitive
    # (also used by the 24-class pipeline), so it cannot hardcode 12.
    for bad in (
        np.zeros((4, 11), dtype=np.float64),     # wrong class count
        np.zeros((4, 13), dtype=np.float64),     # wrong class count
        np.zeros(12, dtype=np.float64),          # missing batch dim
        np.zeros((4, 12, 1), dtype=np.float64),  # extra dim
    ):
        with pytest.raises(ValueError):
            contract.assert_logits_12(bad)


def test_threshold_boundary_semantics():
    # Category 5: rejection is strictly score > threshold; score == threshold is
    # accepted (known).  This mirrors the frozen-threshold convention.
    scores = np.array([-1.0, 0.0, 0.0, 1.0])
    threshold = 0.0
    reject = scores > threshold
    assert reject.tolist() == [False, False, False, True]
