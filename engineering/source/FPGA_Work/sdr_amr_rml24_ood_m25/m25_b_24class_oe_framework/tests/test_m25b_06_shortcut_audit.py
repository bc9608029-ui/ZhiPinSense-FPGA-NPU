"""Generator-shortcut audit tests."""
import pytest

from audit import m25b_shortcut_audit as s


def test_clean_records():
    result = s.audit_shortcut([
        {"modulation": "CW", "source": "far", "family_code": 6, "split_code": 1},
        {"modulation": "GFSK", "source": "near", "family_code": 1, "split_code": 0},
    ])
    assert result["status"] == s.SHORTCUT_CLEAN
    assert result["num_violations"] == 0


def test_id_generator_marker_flagged():
    result = s.audit_shortcut([
        {"modulation": "GMSK", "source": "far", "family_code": 9, "split_code": 1,
         "id_hdf5": "some/path.hdf5"},
    ])
    assert result["status"] == s.SHORTCUT_VIOLATION
    assert result["num_violations"] == 1
    v = result["violations"][0]
    assert v["status"] == s.OOD_PROTOCOL_INVALID
    assert v["reason"] == "generator_shortcut"


def test_id_label_flagged():
    result = s.audit_shortcut([
        {"modulation": "GMSK", "source": "far", "family_code": 9, "split_code": 1,
         "id_label": "GMSK"},
    ])
    assert result["status"] == s.SHORTCUT_VIOLATION


def test_assert_no_shortcut_raises():
    with pytest.raises(RuntimeError):
        s.assert_no_shortcut([
            {"modulation": "GMSK", "source": "far", "family_code": 9,
             "split_code": 1, "id_hdf5": "x"},
        ])
