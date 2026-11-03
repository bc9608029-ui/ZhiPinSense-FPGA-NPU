"""OE data-protocol tests: sources, splits, and the no-25th-class invariant."""
import pytest

from contracts import m25b_oe_data_protocol as p


def test_sources_and_splits():
    assert set(p.OE_SOURCES) == {"near", "far"}
    assert p.OE_SPLITS == ("oe_aux_train", "ood_validation", "ood_final_test")
    assert p.OE_AUX_SPLIT == "oe_aux_train"
    assert set(p.OOD_EVAL_SPLITS) == {"ood_validation", "ood_final_test"}


def test_oe_not_id_label_collision():
    with pytest.raises(ValueError):
        p.assert_oe_not_id_label("GMSK", {"GMSK", "OOK"})
    p.assert_oe_not_id_label("LFM", {"GMSK", "OOK"})  # LFM is not an ID label


def test_oe_sample_record():
    rec = p.oe_sample_record(source="far", family_code=5, modulation="LFM",
                             split_code=1, seed=2026, sample_index=3,
                             sample_length=1024, sample_rate=200000.0,
                             amplitude_rms=1.0)
    assert rec["source"] == "far"
    assert rec["modulation"] == "LFM"
    assert rec["split_code"] == 1
    for key in p.OE_SAMPLE_KEYS:
        assert key in rec


def test_oe_sample_record_rejects_bad_source():
    with pytest.raises(ValueError):
        p.oe_sample_record(source="bogus", family_code=0, modulation="LFM",
                           split_code=1, seed=2026, sample_index=0,
                           sample_length=1024, sample_rate=200000.0,
                           amplitude_rms=1.0)
