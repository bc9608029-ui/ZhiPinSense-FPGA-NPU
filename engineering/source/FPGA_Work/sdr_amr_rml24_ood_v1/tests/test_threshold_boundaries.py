"""M12: threshold helpers handle boundary and empty inputs correctly."""

from __future__ import annotations

import numpy as np
import pytest

from ood.thresholds import id_false_reject_rate, ood_false_accept_rate, select_thresholds


def test_empty_rates_are_nan():
    assert np.isnan(id_false_reject_rate(np.array([]), 0.5))
    assert np.isnan(ood_false_accept_rate(np.array([]), 0.5))


def test_select_thresholds_raises_on_empty():
    with pytest.raises(ValueError):
        select_thresholds(np.array([]), np.array([1.0]))
    with pytest.raises(ValueError):
        select_thresholds(np.array([0.0]), np.array([]))


def test_frr_counts_only_above_threshold():
    assert id_false_reject_rate(np.array([0.0, 1.0, 2.0]), 1.0) == 1.0 / 3.0


def test_far_counts_equal_to_threshold():
    assert ood_false_accept_rate(np.array([0.5, 1.5]), 1.0) == 0.5
