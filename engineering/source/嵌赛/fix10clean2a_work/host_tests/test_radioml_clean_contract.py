"""Host test 1/4 — the synthesis contract (labels, 24->23 map, modulation routing).

Covers §12 items: 5 (label order), 6 (24->23 map), 7 (GMSK/OQPSK routing),
8 (AM-SSB WC/SC independent paths), 11 (per-class RMS non-uniform).
"""

from __future__ import annotations

import numpy as np
import pytest

import radioml_clean_contract as c


def test_label_order_matches_frozen_24():
    assert list(c.LABEL_ORDER_24) == [
        "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
        "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
        "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
        "AM-DSB-SC", "FM", "GMSK", "OQPSK",
    ]


def test_24_to_23_mapping_merges_only_am_ssb():
    from rml23_merged_contract import SOURCE_TO_DEPLOYED, DEPLOYED_LABEL_ORDER_23

    assert len(SOURCE_TO_DEPLOYED) == 24
    assert len(DEPLOYED_LABEL_ORDER_23) == 23
    # identity 0..16
    for i in range(17):
        assert SOURCE_TO_DEPLOYED[i] == i, i
    # AM-SSB-WC (17) and AM-SSB-SC (18) both fold to deployed 17
    assert SOURCE_TO_DEPLOYED[17] == 17
    assert SOURCE_TO_DEPLOYED[18] == 17
    # the rest shift by one (one class removed by the merge)
    assert SOURCE_TO_DEPLOYED[19] == 18   # AM-DSB-WC
    assert SOURCE_TO_DEPLOYED[20] == 19   # AM-DSB-SC
    assert SOURCE_TO_DEPLOYED[21] == 20   # FM
    assert SOURCE_TO_DEPLOYED[22] == 21   # GMSK
    assert SOURCE_TO_DEPLOYED[23] == 22   # OQPSK
    # exactly one pair merged -> 23 distinct deployed classes
    assert len(set(SOURCE_TO_DEPLOYED)) == 23


def test_gmsk_oqpsk_routing_red_line(monkeypatch):
    # source 22 must dispatch to the GMSK generator, 23 to the OQPSK generator.
    seen = []

    def fake_gmsk(rng):
        seen.append("GMSK")
        return ("gmsk", None)

    def fake_oqpsk(rng):
        seen.append("OQPSK")
        return ("oqpsk", None)

    monkeypatch.setattr(c, "_gmsk", fake_gmsk)
    monkeypatch.setattr(c, "_oqpsk", fake_oqpsk)
    assert c.generate_class("GMSK", 1)[0] == "gmsk"
    assert c.generate_class("OQPSK", 2)[0] == "oqpsk"
    assert seen == ["GMSK", "OQPSK"]


def test_gmsk_oqpsk_signals_distinct():
    # §7.4: the two generators produce distinct spectra / phase trajectories / SHA.
    g = c._gmsk(np.random.default_rng(42))
    o = c._oqpsk(np.random.default_rng(42))
    assert g.shape == (c.SAMPLE_LENGTH,)
    assert o.shape == (c.SAMPLE_LENGTH,)
    assert np.all(np.isfinite(g)) and np.all(np.isfinite(o))
    assert not np.allclose(g, o)
    # GMSK is continuous-phase (constant envelope), OQPSK has amplitude ripple.
    assert np.abs(g).std() < 1e-6          # constant envelope
    assert np.abs(o).std() > 0.0


def test_am_ssb_wc_sc_independent_paths():
    # §7.3/§7.4: WC and SC use independent generation paths (different m, different
    # carrier/sideband ratio) and produce different signals.
    wc = c._am_ssb(np.random.default_rng(7), carrier=True)
    sc = c._am_ssb(np.random.default_rng(7), carrier=False)
    assert wc.shape == (c.SAMPLE_LENGTH,) and sc.shape == (c.SAMPLE_LENGTH,)
    assert not np.allclose(wc, sc)

    def sideband_carrier(x):
        dc = float(np.abs(x.mean()))
        rms = float(np.sqrt(np.mean(np.abs(x) ** 2)))
        return np.sqrt(max(rms ** 2 - dc ** 2, 0.0)) / (dc + 1e-12)

    # SC (m=0.09) has a relatively stronger sideband than WC (m=0.06).
    assert sideband_carrier(sc) > sideband_carrier(wc)


def test_per_class_rms_non_uniform():
    # §12 item 11: the contract encodes measured per-class RMS, NOT uniform 1.0.
    assert c.TARGET_RMS["QPSK"] == 1.0
    assert c.TARGET_RMS["GMSK"] == 1.0
    assert c.TARGET_RMS["OQPSK"] == 1.0
    assert c.TARGET_RMS["OOK"] > 1.4
    assert c.TARGET_RMS["4ASK"] > 1.7
    assert c.TARGET_RMS["8ASK"] > 1.9
    assert c.TARGET_RMS["AM-SSB-WC"] > 11.0
    assert c.TARGET_RMS["AM-SSB-SC"] > 7.0


def test_unknown_class_fail_closed():
    with pytest.raises(ValueError):
        c.generate_class("NOT_A_MODULATION", 1)
