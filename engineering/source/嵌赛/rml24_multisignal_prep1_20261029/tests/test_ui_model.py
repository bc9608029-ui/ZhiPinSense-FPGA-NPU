"""Offline UI multi-target list: scan coordinates, selection, clear-on-switch."""

import numpy as np

from src import contracts as C
from src.tracker import TargetTracker
from src.ui_model import SpectrumFrame, UiMultiSignalState


def test_spectrum_frame_scan_coordinates():
    lo = 2_400_000_000
    frame = SpectrumFrame(lo, 12.5, np.zeros(C.FFT_LENGTH))
    assert frame.center_hz(512) == lo
    assert frame.center_hz(549) == lo + 37 * 2500
    assert frame.center_hz(475) == lo - 37 * 2500
    assert frame.freq_axis_hz().size == C.FFT_LENGTH
    assert frame.tune_time_seconds == 12.5


def test_select_replaces_constellation_never_accumulates():
    tr = TargetTracker()
    tr.observe(2_400_000_000, 1.0)
    tr.observe(2_400_250_000, 1.0)
    st = UiMultiSignalState.empty()
    st.refresh(tr.active_targets(), None)
    old_iq = np.array([1 + 1j, 2 + 2j])
    st.select(1, old_iq)
    assert st.selected_target_id == 1
    assert np.array_equal(st.constellation_iq, old_iq)
    st.select(2, None)
    assert st.selected_target_id == 2
    assert st.constellation_iq is None  # switched -> old plot cleared


def test_refresh_drops_vanished_selection_and_clears_constellation():
    tr = TargetTracker()
    tr.observe(2_400_000_000, 1.0)
    st = UiMultiSignalState.empty()
    st.refresh(tr.active_targets(), None)
    st.select(1, np.array([1 + 1j]))
    # Target ages out (3 cycles), then the UI refreshes.
    for _ in range(3):
        tr.end_cycle()
    st.refresh(tr.active_targets(), None)
    assert st.selected_target_id is None
    assert st.constellation_iq is None


def test_select_unknown_target_raises():
    tr = TargetTracker()
    tr.observe(2_400_000_000, 1.0)
    st = UiMultiSignalState.empty()
    st.refresh(tr.active_targets(), None)
    try:
        st.select(999, None)
    except KeyError:
        pass
    else:
        raise AssertionError("selecting an unknown target must fail closed")
