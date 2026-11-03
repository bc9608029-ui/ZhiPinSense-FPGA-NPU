"""Unit tests for the data-v4 robustness scaffolding (fast, no training).

Verifies the frozen twelve-class contract is inherited unchanged, the augmented
channel is confined to ``robust.train_channel``, candidate configs toggle tails
correctly, the robust dataset swaps to the augmented channel only for the train
split, and the formal/lock/packaging entrypoints are wired fail-closed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from channel.channel_pipeline import ChannelPipeline
from channel.robust_augment import RobustChannelPipeline
from datasets.ad_amr_v1_1_dataset import ADAMRV11Dataset
from datasets.ad_amr_v4_robust_dataset import ADAMRV4RobustDataset
from datasets.modulation_generator import V1_1_12_MODULATIONS
from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model
from scripts.lock_robust_formal_config import config_sha256
from scripts.package_ad_amr_v1_1_data_v2_autodl import included_files
from scripts.run_ad_amr_v4_12class_robust_formal import _formal_config
from training.train_ad_amr_v4_12class_robust import (
    _init_from_checkpoint,
    build_robust_dataloaders,
)
from training.utils import load_yaml


def _robust() -> dict:
    return load_yaml("configs/ad_amr_v1_1_data_v4_12class_robust.yaml")


def _v3() -> dict:
    return load_yaml("configs/ad_amr_v1_1_data_v3_12class.yaml")


# --- frozen-contract inheritance -------------------------------------------------

def test_robust_inherits_frozen_twelve_class_contract() -> None:
    robust, v3 = _robust(), _v3()
    assert tuple(robust["signal"]["modulations"]) == V1_1_12_MODULATIONS
    assert robust["signal"]["sample_length"] == 1024
    assert robust["signal"] == v3["signal"]
    assert robust["model"] == v3["model"]
    assert robust["acceptance"] == v3["acceptance"]
    assert robust["channel"] == v3["channel"]
    assert robust["acceptance"]["gates"]["max_ood_macro_f1_drop"] == 0.08
    assert robust["acceptance"]["gates"]["mean_full_macro_f1"] == 0.72


def test_robust_status_is_provisional_until_approved() -> None:
    robust = _robust()
    assert robust["robust"]["status"] == "PROVISIONAL"
    assert robust["robust"]["final_config_approved"] is False
    assert robust["robust"]["pilot"]["min_improvement"] == {
        "cfo_strong": 0.0446, "multipath": 0.0378, "multi_impairment": 0.0522,
    }


def test_augmented_channel_is_confined_to_train_channel_section() -> None:
    robust = _robust()
    # The frozen `channel` (validation/OOD) is untouched; augmentation lives only
    # under `robust.train_channel`, so it cannot pollute the frozen evaluator.
    assert "tail" not in robust["channel"]["cfo"]
    assert "composite" not in robust["channel"]
    assert "tail" in robust["robust"]["train_channel"]["cfo"]
    assert "composite" in robust["robust"]["train_channel"]


# --- candidate configs -------------------------------------------------------------

def test_candidate_a_enables_only_cfo_tail() -> None:
    config = load_yaml("configs/ad_amr_v1_1_data_v4_12class_robust_pilot_A.yaml")
    assert config["robust"]["candidate"] == "A"
    train = config["robust"]["train_channel"]
    assert train["cfo"]["tail"]["probability"] == 0.20
    assert train["multipath"]["tail"]["probability"] == 0.0
    assert train["composite"]["enabled"] is False


def test_candidate_b_disables_cfo_tail_keeps_multipath_and_composite() -> None:
    config = load_yaml("configs/ad_amr_v1_1_data_v4_12class_robust_pilot_B.yaml")
    train = config["robust"]["train_channel"]
    assert config["robust"]["candidate"] == "B"
    assert train["cfo"]["tail"]["probability"] == 0.0
    assert train["multipath"]["tail"]["probability"] == 0.15
    assert train["composite"]["enabled"] is True


def test_candidate_c_enables_all_three_mechanisms() -> None:
    config = load_yaml("configs/ad_amr_v1_1_data_v4_12class_robust_pilot_C.yaml")
    train = config["robust"]["train_channel"]
    assert config["robust"]["candidate"] == "C"
    assert train["cfo"]["tail"]["probability"] == 0.20
    assert train["multipath"]["tail"]["probability"] == 0.15
    assert train["composite"]["enabled"] is True


# --- dataset / dataloader split isolation ------------------------------------------

def test_robust_dataloader_train_uses_augmented_val_uses_frozen() -> None:
    config = load_yaml("configs/ad_amr_v1_1_data_v4_12class_robust_smoke.yaml")
    train, val = build_robust_dataloaders(config, __import__("torch").device("cpu"))
    assert isinstance(train.dataset, ADAMRV4RobustDataset)
    assert isinstance(train.dataset.channel, RobustChannelPipeline)
    assert isinstance(val.dataset, ADAMRV11Dataset)
    assert isinstance(val.dataset.channel, ChannelPipeline)
    assert "robust_train" in train.dataset.split
    assert val.dataset.split == "ad_amr_v1_1_validation"


# --- init / formal / lock / packaging ----------------------------------------------

def test_init_from_checkpoint_fails_closed_when_missing() -> None:
    config = _robust()
    model = build_ad_amr_v1_1_model(12, **config["model"])
    with pytest.raises(FileNotFoundError):
        _init_from_checkpoint(model, "outputs/ad_amr_v1_1_data_v3_12class/formal/"
                              "seed2026/checkpoints/does_not_exist.pt", V1_1_12_MODULATIONS)


def test_formal_config_locks_two_seeds_and_low_lr() -> None:
    robust = _robust()
    config = _formal_config(robust, 2026)
    assert config["output_root"].endswith("formal/seed2026")
    assert config["training"]["epochs"] == 100
    assert config["training"]["minimum_epochs_before_stopping"] == 30
    assert config["training"]["learning_rate"] == 0.0001
    assert _formal_config(robust, 2027)["output_root"].endswith("formal/seed2027")


def test_config_sha256_is_deterministic() -> None:
    payload = {"robust": {"candidate": "C", "final_config_approved": True}}
    assert config_sha256(payload) == config_sha256(payload)


def test_package_includes_robustness_entrypoints() -> None:
    root = Path(__file__).resolve().parents[1]
    names = {path.relative_to(root).as_posix() for path in included_files()}
    for expected in (
        "scripts/run_ad_amr_v4_12class_robust_pilot.py",
        "scripts/run_ad_amr_v4_12class_robust_formal.py",
        "scripts/lock_robust_formal_config.py",
        "scripts/collect_formal_predictions.py",
        "autodl_ad_amr_v1_1_data_v4_12class_robust/run_preflight.sh",
        "autodl_ad_amr_v1_1_data_v4_12class_robust/run_pilot.sh",
        "autodl_ad_amr_v1_1_data_v4_12class_robust/run_lock.sh",
        "autodl_ad_amr_v1_1_data_v4_12class_robust/run_formal.sh",
    ):
        assert expected in names
