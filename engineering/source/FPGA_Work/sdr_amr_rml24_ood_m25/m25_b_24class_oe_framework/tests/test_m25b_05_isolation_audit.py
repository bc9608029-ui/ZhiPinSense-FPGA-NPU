"""Three-way isolation audit tests."""
import pytest

from audit import m25b_isolation_audit as a


def _rec(mod, src, fc, split_name, sha=None):
    code = {"oe_aux_train": 0, "ood_validation": 1, "ood_final_test": 2}[split_name]
    rec = {"modulation": mod, "source": src, "family_code": fc,
           "split_code": code, "split_name": split_name}
    if sha is not None:
        rec["samples_sha256"] = sha
    return rec


def test_same_modulation_across_splits_is_ok():
    # The same family legitimately appears in every split with distinct samples.
    records = [
        _rec("LFM", "far", 5, "oe_aux_train", sha="a" * 64),
        _rec("LFM", "far", 5, "ood_validation", sha="b" * 64),
        _rec("LFM", "far", 5, "ood_final_test", sha="c" * 64),
        _rec("2FSK", "near", 0, "oe_aux_train", sha="d" * 64),
    ]
    result = a.audit_isolation(records)
    assert result["status"] == a.ISOLATION_OK
    assert result["num_violations"] == 0
    assert result["counts_by_split"]["ood_validation"]["LFM"] == 1


def test_split_mapping_mismatch_flagged():
    records = [
        {"modulation": "LFM", "source": "far", "family_code": 5,
         "split_code": 0, "split_name": "ood_validation"},  # code 0 must be oe_aux
    ]
    result = a.audit_isolation(records)
    assert result["status"] == a.ISOLATION_VIOLATION
    assert any(v["reason"] == "split_mapping_mismatch" for v in result["violations"])


def test_sample_leakage_flagged():
    records = [
        _rec("LFM", "far", 5, "oe_aux_train", sha="deadbeef" * 8),
        _rec("LFM", "far", 5, "ood_validation", sha="deadbeef" * 8),  # same sample
    ]
    result = a.audit_isolation(records)
    assert result["status"] == a.ISOLATION_VIOLATION
    assert any(v["reason"] == "sample_leakage" for v in result["violations"])


def test_bad_split_flagged():
    records = [{"modulation": "LFM", "source": "far", "family_code": 5,
                "split_code": 9, "split_name": "bogus_split"}]
    result = a.audit_isolation(records)
    assert result["status"] == a.ISOLATION_VIOLATION


def test_assert_isolated_raises():
    records = [
        {"modulation": "LFM", "source": "far", "family_code": 5,
         "split_code": 1, "split_name": "oe_aux_train"},  # mismatch
    ]
    with pytest.raises(RuntimeError):
        a.assert_isolated(records)
