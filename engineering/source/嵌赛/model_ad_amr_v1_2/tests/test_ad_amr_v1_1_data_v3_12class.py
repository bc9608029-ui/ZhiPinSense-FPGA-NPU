from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pytest
import torch

from datasets.ad_amr_v1_1_dataset import ADAMRV11Dataset, assert_v1_1_signal_contract
from datasets.modulation_generator import V1_1_12_MODULATIONS, generate_iq
from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model
from models.ad_amr_v1_1_teachers import OLD_CLASSES
from training.ad_amr_v1_1_loss import teacher_student_class_mapping
from training.train_ad_amr_v1_1_data_v3_12class import assert_twelve_class_contract
from training.utils import load_yaml
from scripts.package_ad_amr_v1_1_data_v3_12class_autodl import included_files
from scripts.run_ad_amr_v1_1_data_v3_12class_formal import _formal_config


def test_twelve_class_config_is_frozen_balanced_and_keeps_strict_gates() -> None:
    config = load_yaml("configs/ad_amr_v1_1_data_v3_12class.yaml")
    assert tuple(config["signal"]["modulations"]) == V1_1_12_MODULATIONS
    assert config["dataset"]["train_samples"] == 21 * 12 * 150
    assert config["dataset"]["val_samples"] == 21 * 12 * 30
    assert config["training"]["distillation"]["class_aliases"] is None
    assert config["acceptance"]["gates"]["mean_full_macro_f1"] == 0.72
    assert config["acceptance"]["gates"]["each_seed_new_ask_rated_accuracy"] == 0.75
    assert_twelve_class_contract(config)


def test_ook_and_4ask_are_deterministic_finite_normalized_and_distinct() -> None:
    config = load_yaml("configs/ad_amr_v1_1_data_v3_12class.yaml")["signal"]
    records = {}
    for name in ("OOK", "4ASK"):
        first, metadata = generate_iq(name, config, np.random.default_rng(1234))
        second, _ = generate_iq(name, config, np.random.default_rng(1234))
        assert np.array_equal(first, second)
        assert first.shape == (1024,) and first.dtype == np.complex64
        assert np.isfinite(first).all()
        assert np.isclose(np.sqrt(np.mean(np.abs(first) ** 2)), 1.0, atol=1e-5)
        assert metadata["modulation"] == name
        records[name] = first
    assert not np.array_equal(records["OOK"], records["4ASK"])


def test_balanced_grid_contains_every_class_at_every_snr_once() -> None:
    config = load_yaml("configs/ad_amr_v1_1_data_v3_12class.yaml")
    snrs = config["dataset"]["snr_values"]
    dataset = ADAMRV11Dataset(
        len(snrs) * len(V1_1_12_MODULATIONS), config["signal"], None, 7,
        "ad_amr_v1_1_data_v3_validation_balance", snr_values=snrs,
    )
    counts = Counter((dataset[index]["label"], dataset[index]["snr_db"])
                     for index in range(len(dataset)))
    assert len(counts) == len(snrs) * len(V1_1_12_MODULATIONS)
    assert set(counts.values()) == {1}


def test_distillation_mapping_is_name_based_after_two_classes_are_prepended() -> None:
    pairs = teacher_student_class_mapping(V1_1_12_MODULATIONS)
    by_teacher = {OLD_CLASSES[teacher]: student for teacher, student in pairs}
    assert by_teacher == {
        "BPSK": 6, "QPSK": 7, "8PSK": 8, "16QAM": 9,
        "64QAM": 10, "2FSK": 4, "OFDM": 11,
    }
    assert "CPFSK" not in by_teacher


def test_twelve_class_model_output_and_wrong_order_fail_closed() -> None:
    config = load_yaml("configs/ad_amr_v1_1_data_v3_12class.yaml")
    model = build_ad_amr_v1_1_model(12, **config["model"])
    logits, denoised = model(torch.zeros(2, 2, 1024))
    assert logits.shape == (2, 12)
    assert denoised.shape == (2, 2, 1024)
    wrong = dict(config["signal"])
    wrong["modulations"] = list(reversed(V1_1_12_MODULATIONS))
    with pytest.raises(ValueError, match="approved fixed class order"):
        assert_v1_1_signal_contract(wrong)
    bad_config = dict(config)
    bad_config["signal"] = wrong
    with pytest.raises(RuntimeError, match="fixed twelve-class order"):
        assert_twelve_class_contract(bad_config)


def test_legacy_ten_class_alias_is_explicit_but_twelve_class_has_none() -> None:
    legacy = load_yaml("configs/ad_amr_v1_1.yaml")
    current = load_yaml("configs/ad_amr_v1_1_data_v3_12class.yaml")
    assert legacy["training"]["distillation"]["class_aliases"] == {"CPFSK": "GFSK"}
    assert current["training"]["distillation"]["class_aliases"] is None


def test_formal_is_two_seed_and_source_package_contains_twelve_class_entrypoints() -> None:
    base = load_yaml("configs/ad_amr_v1_1_data_v3_12class.yaml")
    assert base["data_v3_formal"]["seeds"] == [2026, 2027]
    assert _formal_config(base, 2026)["output_root"].endswith("formal/seed2026")
    assert _formal_config(base, 2027)["output_root"].endswith("formal/seed2027")
    root = Path(__file__).resolve().parents[1]
    names = {path.relative_to(root).as_posix() for path in included_files()}
    assert "autodl_ad_amr_v1_1_data_v3_12class/run_preflight.sh" in names
    assert "autodl_ad_amr_v1_1_data_v3_12class/run_formal.sh" in names
    assert "scripts/run_ad_amr_v1_1_data_v3_12class_formal.py" in names
