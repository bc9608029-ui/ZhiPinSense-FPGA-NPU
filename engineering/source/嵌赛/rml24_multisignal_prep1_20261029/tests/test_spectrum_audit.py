"""TX composite spectrum audit: crest/clip, guard band, IM3, cross-talk."""

import numpy as np

from src import contracts as C
from src import spectrum_audit as audit
from src import tx_synth


def _build(*offsets, spacing=200_000):
    carriers = [tx_synth.TxCarrier(offset_hz=o) for o in offsets]
    composite, per_carrier = tx_synth.synthesize(carriers)
    return composite, per_carrier, carriers


def test_two_well_separated_carriers_pass_guard():
    composite, per_carrier, carriers = _build(-200_000, +200_000)
    res = audit.run_audit(composite, carriers, per_carrier)
    assert res.n_carriers == 2
    assert res.guard_ok
    assert res.min_guard_hz == 400_000
    assert res.papr_db > 0.0
    assert res.clip_fraction == 0.0  # no clipping at unit amplitude sum


def test_guard_violation_when_too_close():
    composite, per_carrier, carriers = _build(0, 5_000)
    res = audit.run_audit(composite, carriers, per_carrier)
    assert not res.guard_ok
    assert res.min_guard_hz == 5_000


def test_im3_below_carriers():
    composite, per_carrier, carriers = _build(-200_000, +200_000)
    res = audit.run_audit(composite, carriers, per_carrier)
    assert res.im3_relative_db < 0.0  # IM3 products below the carriers


def test_cross_interference_is_bounded_for_separated_carriers():
    composite, per_carrier, carriers = _build(-200_000, +200_000)
    res = audit.run_audit(composite, carriers, per_carrier)
    for c in res.carriers:
        # leakage from the other carrier inside this carrier's band is far below it
        assert c.leakage_from_others_db < -20.0


def test_papr_grows_with_more_carriers():
    # Uncorrelated carriers add power (RMS ~ sqrt(N)) and peak (~ N worst case),
    # so the crest factor grows with the carrier count -- the reason the frozen
    # envelope caps the number of simultaneous carriers within one TX band.
    two = tx_synth.synthesize([tx_synth.TxCarrier(-200_000), tx_synth.TxCarrier(+200_000)])[0]
    many = tx_synth.synthesize([
        tx_synth.TxCarrier(-300_000), tx_synth.TxCarrier(-100_000),
        tx_synth.TxCarrier(+100_000), tx_synth.TxCarrier(+300_000),
    ])[0]
    papr_two = audit.crest_and_clipping(two)[2]
    papr_many = audit.crest_and_clipping(many)[2]
    assert papr_many > papr_two
