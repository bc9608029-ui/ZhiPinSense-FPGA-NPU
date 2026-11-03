"""Contract tests: frozen 24-class order, I/O shape, and SHA constants."""
import pytest

from contracts import m25b_24class_contract as c


def test_label_order_24_frozen():
    assert len(c.LABEL_ORDER_24) == 24
    assert c.LABEL_ORDER_24[0] == "OOK"
    assert c.LABEL_ORDER_24[23] == "OQPSK"
    assert c.LABEL_ORDER_24[16] == "256QAM"
    # No duplicates in the frozen order.
    assert len(set(c.LABEL_ORDER_24)) == 24


def test_io_contract():
    assert c.INPUT_SHAPE == (1, 2, 1024)
    assert c.OUTPUT_DIM == 24
    assert c.OUTPUT_KIND == "raw_logits_no_softmax"


def test_sha_constants_are_64_hex():
    for name, value in (
        ("DATASET_HDF5_SHA256", c.DATASET_HDF5_SHA256),
        ("DATASET_INDEX_SHA256", c.DATASET_INDEX_SHA256),
        ("CLASSES_TXT_SHA256", c.CLASSES_TXT_SHA256),
        ("TWELVE_CLASS_MODEL_SHA256", c.TWELVE_CLASS_MODEL_SHA256),
    ):
        assert len(value) == 64, name
        assert all(ch in "0123456789abcdef" for ch in value), name


def test_assert_24class_order():
    assert c.assert_24class_order(c.LABEL_ORDER_24) == c.LABEL_ORDER_24
    reordered = (c.LABEL_ORDER_24[1],) + c.LABEL_ORDER_24[:1] + c.LABEL_ORDER_24[2:]
    with pytest.raises(ValueError):
        c.assert_24class_order(reordered)


def test_assert_not_final_status():
    for marker in c.FORBIDDEN_STATUS_MARKERS:
        with pytest.raises(RuntimeError):
            c.assert_not_final_status(marker)
    c.assert_not_final_status("24CLASS_OE_FRAMEWORK_READY")  # allowed ceiling
