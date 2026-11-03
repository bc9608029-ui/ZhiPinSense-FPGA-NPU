"""M1: the frozen 24-class label order must be byte-consistent everywhere."""

from __future__ import annotations

import json

import pytest

from contracts.rml24_contract import LABEL_ORDER_24, assert_24class_order
from datasets.radioml2018_dataset import OFFICIAL_CLASS_ORDER
from training.utils import resolve_project_path

EXPECTED = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)


def test_contract_order_is_expected():
    assert LABEL_ORDER_24 == EXPECTED
    assert len(LABEL_ORDER_24) == 24
    assert len(set(LABEL_ORDER_24)) == 24


def test_contract_order_matches_dataset_official_order():
    assert OFFICIAL_CLASS_ORDER == LABEL_ORDER_24


def test_classes_txt_matches_contract():
    text = resolve_project_path("data/radioml2018/classes.txt").read_text(encoding="utf-8").strip()
    lines = [line for line in text.splitlines() if line.strip()]
    assert lines == list(EXPECTED)


def test_24_labels_json_matches_contract():
    payload = json.loads(resolve_project_path("contracts/rml2018_24_labels.json").read_text(encoding="utf-8"))
    assert payload["labels"] == list(EXPECTED)
    assert payload["num_classes"] == 24


def test_assert_24class_order_accepts_frozen_order():
    assert assert_24class_order(EXPECTED) == EXPECTED
    assert assert_24class_order([name.lower() for name in EXPECTED]) == EXPECTED


def test_assert_24class_order_rejects_reorder():
    with pytest.raises(ValueError):
        assert_24class_order(list(reversed(EXPECTED)))
