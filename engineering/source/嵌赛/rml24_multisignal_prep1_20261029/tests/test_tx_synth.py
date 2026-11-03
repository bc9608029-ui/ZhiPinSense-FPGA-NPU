"""TX digital-domain synthesis primitives (task 4)."""

import numpy as np
import pytest

from src import contracts as C
from src import tx_synth


def test_common_frame_unit_rms():
    frame = tx_synth.make_common_frame()
    assert frame.size == C.FRAME_SAMPLES
    rms = np.sqrt(np.mean(np.abs(frame) ** 2))
    assert abs(rms - 1.0) < 0.01


def test_synthesize_sums_carriers():
    carriers = [
        tx_synth.TxCarrier(offset_hz=-100_000, amplitude=1.0),
        tx_synth.TxCarrier(offset_hz=+100_000, amplitude=1.0),
    ]
    composite, per_carrier = tx_synth.synthesize(carriers)
    assert composite.shape == (C.FRAME_SAMPLES,)
    assert per_carrier.shape == (2, C.FRAME_SAMPLES)
    rms_single = np.sqrt(np.mean(np.abs(per_carrier[0]) ** 2))
    rms_sum = np.sqrt(np.mean(np.abs(composite) ** 2))
    assert rms_sum > rms_single  # two uncorrelated carriers add power


def test_to_int16_clipped_is_in_range():
    composite, _ = tx_synth.synthesize([tx_synth.TxCarrier(0)])
    i16, scale = tx_synth.to_int16_clipped(composite)
    assert i16.dtype == np.int16
    assert i16.size == 2 * composite.size
    assert np.max(np.abs(i16)) <= C.TX_FULL_SCALE
    assert scale > 0.0


def test_carrier_offset_must_be_inside_usable_band():
    with pytest.raises(ValueError):
        tx_synth.TxCarrier(offset_hz=C.TX_USABLE_HALF_BAND_HZ + 1)
    tx_synth.TxCarrier(offset_hz=C.TX_USABLE_HALF_BAND_HZ)


def test_synthesize_rejects_mismatched_frame_lengths():
    long_frame = tx_synth.make_common_frame(samples=C.FRAME_SAMPLES + 64)
    carriers = [
        tx_synth.TxCarrier(offset_hz=-100_000),
        tx_synth.TxCarrier(offset_hz=+100_000, frame=long_frame),
    ]
    with pytest.raises(ValueError):
        tx_synth.synthesize(carriers)
