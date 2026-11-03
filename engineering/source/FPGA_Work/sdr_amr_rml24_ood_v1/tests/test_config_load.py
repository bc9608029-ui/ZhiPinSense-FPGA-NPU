"""M5/M13: all configs load, the smoke config inherits the base, and OE is wired."""

from __future__ import annotations

import pytest

from training.utils import load_yaml

CONFIG_FILES = [
    "configs/rml24_base.yaml",
    "configs/rml24_smoke.yaml",
    "configs/search_space_rml24.yaml",
    "configs/oe_energy.yaml",
]


@pytest.mark.parametrize("rel", CONFIG_FILES)
def test_config_loads(rel):
    assert isinstance(load_yaml(rel), dict)


def test_smoke_inherits_base():
    cfg = load_yaml("configs/rml24_smoke.yaml")
    assert "model" in cfg and "training" in cfg and "rml24" in cfg
    assert cfg["training"]["epochs"] == 3
    assert cfg["model"]["denoiser_channels"] == 24  # inherited from base
    assert cfg["rml24"]["smoke_max_per_stratum"] == 4


def test_oe_energy_block_wired():
    cfg = load_yaml("configs/oe_energy.yaml")
    assert cfg["oe_energy"]["enabled"] is True
    assert cfg["oe_energy"]["temperature"] == 1.0
    assert cfg["rml24"]["model_name"] == "RML2018_24_ROBUST_CANDIDATE"


def test_search_space_within_budget():
    search = load_yaml("configs/search_space_rml24.yaml")["search"]
    assert search["n_pilot_trials"] <= 12
    assert len(search["formal_seeds"]) == 3
    assert search["formal_epochs"] >= search["pilot_epochs"]
