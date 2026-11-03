"""M0/M1/M2: every contract JSON parses and cross-references consistently."""

from __future__ import annotations

import json

import pytest

from contracts.rml24_contract import LABEL_ORDER_24
from training.utils import resolve_project_path

CONTRACT_FILES = [
    "contracts/rml2018_24_labels.json",
    "contracts/rml2018_input_contract.json",
    "contracts/rml2018_split_contract.json",
    "contracts/rml2018_data_contract.json",
    "contracts/12class_import_contract.json",
    "contracts/COMMON_LABELS.json",
    "contracts/AMBIGUOUS_LABELS.json",
    "contracts/PREPROCESS_CONTRACT.json",
]


def _read(rel: str) -> dict:
    return json.loads(resolve_project_path(rel).read_text(encoding="utf-8"))


@pytest.mark.parametrize("rel", CONTRACT_FILES)
def test_contract_json_parses(rel):
    assert isinstance(_read(rel), dict)


def test_common_labels_in_both_orders():
    common = _read("contracts/COMMON_LABELS.json")["labels"]
    labels_12 = _read("contracts/12class_import_contract.json")["label_order_12"]
    assert len(common) == 7
    assert set(common) <= set(labels_12)
    assert set(common) <= set(LABEL_ORDER_24)


def test_ambiguous_pairs_reference_known_labels():
    ambiguous = _read("contracts/AMBIGUOUS_LABELS.json")["pairs"]
    labels_12 = set(_read("contracts/12class_import_contract.json")["label_order_12"])
    labels_24 = set(LABEL_ORDER_24)
    assert len(ambiguous) >= 4
    for pair in ambiguous:
        assert pair["name_12"] in labels_12
        assert pair["name_24"] in labels_24


def test_12class_contract_shape_and_dim():
    contract = _read("contracts/12class_import_contract.json")
    assert contract["input_shape"] == [1, 2, 1024]
    assert contract["output_dim"] == 12
    assert len(contract["label_order_12"]) == 12
