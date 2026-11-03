"""Same-capture multi-signal coverage (C4).

Two honest, separate claims live here:

1. The REAL public frame is FULL-BAND QPSK (verified in this file's audit):
   its train/tail occupy ~1.00x fs, NOT <=10 kHz.  Multiple real public frames
   superimposed in ONE capture overlap almost completely in frequency, so a
   single ``detect_public_training`` returns ONE hit -- same-dwell multi-target
   is NOT claimed for the correlation primitive.
2. The software PSD backend (``psd.pick_peaks`` -> ``sweep_psd``) can return
   SEVERAL candidates from one capture, but only for spectrally separable
   carriers (narrow-band stand-ins, explicitly NOT the real public frame).
   12.5 kHz separability remains an offline test target, not a promise.

The ``home_map`` replay in test_real_entry_replay.py is a CONTROLLED SCHEDULING
fixture (each emitter is present only at its nearest LO), not evidence of
simultaneous same-capture reception; it is retained there with that scope.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))
sys.path.insert(0, str(ROOT))

from candidate_two_dc import train as PUBLIC_TRAIN, tail as PUBLIC_TAIL  # noqa: E402
from scan_runtime import detect_public_training  # noqa: E402

from src.psd import pick_peaks, windowed_psd_linear  # noqa: E402
from src.scan_adapter import MultiSignalScanLoop  # noqa: E402

FS = 2_560_000
CAPTURE = 65_536
BIN_HZ = FS // 1024


# --- real public-frame audit ------------------------------------------------
def _occupied_bw_hz(iq: np.ndarray, db_down: float = 20.0) -> float:
    power = windowed_psd_linear(iq)
    peak = float(power.max())
    db = 10.0 * np.log10(np.maximum(power, peak * 1e-8))
    active = np.flatnonzero(db >= db.max() - db_down)
    return float((active[-1] - active[0] + 1) * BIN_HZ)


def test_real_public_frame_is_full_band_not_10khz():
    train = np.asarray(PUBLIC_TRAIN, dtype=np.complex128)
    bw = _occupied_bw_hz(train)
    # Full-band QPSK: -20 dB occupied bandwidth is essentially the whole Nyquist
    # band, definitively NOT the <=10 kHz narrow-band stand-in.
    assert bw > 0.9 * FS
    assert bw < 1.1 * FS


# --- same capture: real full-band frames -> single detection only -----------
def _payload() -> np.ndarray:
    rng = np.random.default_rng(7)
    return np.exp(1j * (np.pi / 4 + np.pi / 2 * rng.integers(0, 4, 1024))).astype(np.complex64)


def _public_frame(cfo_hz: float) -> np.ndarray:
    train = np.asarray(PUBLIC_TRAIN, dtype=np.complex128)
    tail = np.asarray(PUBLIC_TAIL, dtype=np.complex128)
    body = np.concatenate([np.zeros(2048), train, np.tile(_payload(), 8), tail, np.zeros(2048)])
    n = np.arange(body.size, dtype=np.float64)
    return body * np.exp(2j * np.pi * float(cfo_hz) * n / FS)


def test_same_capture_full_band_frames_single_detect_only():
    """Two full-band public frames in ONE capture: the correlation primitive
    returns ONE hit, so same-dwell multi-target is NOT claimed here."""
    lo = 2_400_000_000
    x = np.zeros(CAPTURE, dtype=np.complex128)
    frame = _public_frame(0.0)
    assert frame.size == 16384          # 2048 zero + 2048 train + 8192 payload
                                        # + 2048 tail + 2048 zero
    x[8192:8192 + frame.size] += frame
    x[8192:8192 + frame.size] += _public_frame(250_000.0)   # second frame, +250 kHz
    d = detect_public_training(np.asarray(x), PUBLIC_TRAIN)
    assert d.score >= 0.10                       # some frame IS detected
    # One detection, one CFO estimate -- the primitive does not enumerate peers.
    assert not hasattr(d, "peers")
    # Same-capture multi-target therefore requires the PSD candidate path, not
    # this primitive; this test guards against claiming otherwise.


# --- software PSD multi-candidate: narrow-band stand-ins --------------------
class FakeRadio:
    def __init__(self) -> None:
        self.lo = 0
        self.buf = np.zeros(CAPTURE, dtype=np.complex128)

    def tune(self, hz: int) -> int:
        self.lo = int(hz)
        return self.lo

    def flush(self) -> None:
        pass

    def capture(self) -> np.ndarray:
        return self.buf


def _tones(offsets_amp: list[tuple[int, float]], n: int = 4096) -> np.ndarray:
    x = np.zeros(n, dtype=np.complex128)
    for off, amp in offsets_amp:
        x += amp * np.exp(2j * np.pi * off * np.arange(n) / FS)
    return x


def _run_psd(offsets_amp, lo=2_400_000_000):
    radio = FakeRadio()
    radio.buf = _tones(offsets_amp)
    loop = MultiSignalScanLoop([lo])
    new = loop.sweep_psd(pick_peaks, radio.tune, radio.capture, radio.flush, 1.0)
    return loop, new


def test_psd_multi_candidate_zero_one_two_three():
    # 0 targets: noise only.
    loop, new = _run_psd([], )
    assert new == [] and loop.active_targets() == []

    # 1 target.
    loop, new = _run_psd([(0.0, 1.0)])
    assert len(new) == 1

    # 2 targets, far apart.
    loop, new = _run_psd([(-50_000, 1.0), (+50_000, 1.0)])
    assert len(new) == 2
    assert sorted(t.center_hz for t in loop.active_targets()) == \
        [2_399_950_000, 2_400_050_000]

    # 3 targets.
    loop, new = _run_psd([(-50_000, 1.0), (0.0, 1.0), (+50_000, 1.0)])
    assert len(new) == 3


def test_psd_multi_candidate_overlap_unresolvable():
    # Two equal-power tones 5 kHz apart (2 bins, well inside the 12.5 kHz /
    # 5-bin offline target) merge into ONE candidate: this is the honest
    # "unresolvable" outcome, never two fabricated targets.  (In ideal,
    # noiseless conditions the software PSD actually resolves ~4 bins apart, so
    # the 12.5 kHz target is deliberately conservative -- not a promise.)
    loop, new = _run_psd([(-2_500, 1.0), (+2_500, 1.0)])
    assert len(new) == 1


def test_psd_multi_candidate_strong_weak():
    # Weak tone 30 dB below a strong tone, far apart -> weak survives.
    loop, new = _run_psd([(-50_000, 1.0), (+50_000, 10 ** (-30.0 / 20.0))])
    assert len(new) == 2
    powers = sorted(t.power_valid for t in loop.active_targets())
    assert powers[0] < powers[1]           # weaker target has lower prominence


def test_psd_multi_candidate_band_edge():
    # Within the usable half-band (+1.0 MHz) the tone is found.
    loop, new = _run_psd([(+1_000_000, 1.0)])
    assert len(new) == 1
