"""M20 test categories 6-7: UNKNOWN semantics + NO_SIGNAL/ERROR distinction.

These are the decision-state semantics mirrored by cpp/ood_u_contract.hpp and
the CPU-side detector.  Pure Python assertions on the frozen sentinels.
"""

from __future__ import annotations

from ood_u import contract


def test_unknown_distinct_from_known_classes():
    # Category 6: UNKNOWN must not collide with any frozen known-class name.
    assert contract.UNKNOWN == "UNKNOWN"
    assert contract.UNKNOWN not in contract.LABEL_ORDER_12


def test_no_signal_vs_unknown_vs_error_distinct():
    # Category 7: the three non-class states are pairwise distinct and none is a
    # known class; EMPTY is the empty string and distinct from all of them.
    states = {contract.UNKNOWN, contract.NO_SIGNAL, contract.ERROR}
    assert len(states) == 3
    assert contract.EMPTY == ""
    assert contract.EMPTY not in states
    for state in states:
        assert state not in contract.LABEL_ORDER_12
        assert state != contract.EMPTY
