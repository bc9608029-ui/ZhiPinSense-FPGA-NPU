"""Status red lines: final markers must raise, pre-training markers must not."""

from __future__ import annotations

import pytest

from contracts.rml24_contract import FORBIDDEN_STATUS_MARKERS, assert_not_final_status


@pytest.mark.parametrize("marker", FORBIDDEN_STATUS_MARKERS)
def test_forbidden_status_raises(marker):
    with pytest.raises(RuntimeError):
        assert_not_final_status(marker)


def test_forbidden_markers_are_defined():
    assert len(FORBIDDEN_STATUS_MARKERS) >= 5
    assert "HARDWARE_PASS" in FORBIDDEN_STATUS_MARKERS
    assert "FINAL_MODEL_PASS" in FORBIDDEN_STATUS_MARKERS


def test_pre_training_markers_are_allowed():
    assert_not_final_status("READY-FOR-AUTODL-RML24-AND-OOD-TRAINING")
    assert_not_final_status("READY-FOR-12-VS-24-MODEL-SELECTION")
    assert_not_final_status("OOD_SEEN-OUTLIER_ONLY")
