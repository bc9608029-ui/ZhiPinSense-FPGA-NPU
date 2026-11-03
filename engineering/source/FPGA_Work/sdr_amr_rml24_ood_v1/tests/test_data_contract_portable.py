"""M1: the data contract's portable facts are internally consistent."""

from __future__ import annotations

import json
import re

from contracts.rml24_contract import LABEL_ORDER_24
from training.utils import resolve_project_path


def _read():
    return json.loads(resolve_project_path("contracts/rml2018_data_contract.json").read_text(encoding="utf-8"))


def test_portable_facts():
    data = _read()
    assert data["status"] == "pass"
    assert data["dataset"] == "RadioML2018.01A"
    assert data["samples"] == 2555904
    assert data["num_classes"] == 24
    assert data["class_names"] == list(LABEL_ORDER_24)
    assert sum(data["split_counts"].values()) == data["samples"]
    assert data["overlap_counts"] == {"train_validation": 0, "train_test": 0, "validation_test": 0}
    assert data["synthetic_fallback"] is False
    assert data["strata"]["count"] == data["strata"]["expected"] == 624


def test_sha256_fields_are_well_formed():
    data = _read()
    assert re.fullmatch(r"[0-9a-f]{64}", data["sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", data["index_sha256"])


def test_split_contract_matches_data_contract():
    split = json.loads(resolve_project_path("contracts/rml2018_split_contract.json").read_text(encoding="utf-8"))
    data = _read()
    assert split["split_ratios"] == [0.6, 0.2, 0.2]
    assert split["split_seed"] == data["split_seed"] == 20261003
    assert split["leakage_free"] is True
    assert split["overlap"] == {"train_validation": 0, "train_test": 0, "validation_test": 0}
