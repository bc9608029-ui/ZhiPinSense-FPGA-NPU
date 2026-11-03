from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest
import torch

from datasets.ad_amr_v1_1_dataset import ADAMRV11Dataset
from datasets.ad_amr_v1_2_dataset import ADAMRV12Dataset
from evaluation.evaluate_ad_amr_v1_2 import ood_channels
from scripts.export_ad_amr_v1_2_onnx import export_v1_2
from scripts.run_ad_amr_v1_2_pilot import variant_config
from training.ad_amr_v1_2_trainer import training_signature
from training.train_ad_amr_v1_2 import run_v1_2_training
from training.utils import load_yaml


def test_disabled_curriculum_is_byte_identical_to_v1_1_data() -> None:
    config = load_yaml("configs/ad_amr_v1_2_smoke.yaml")
    snrs = config["dataset"]["snr_values"]
    old = ADAMRV11Dataset(32, config["signal"], config["channel"], 2026,
                          "ad_amr_v1_1_train", snr_values=snrs)
    new = ADAMRV12Dataset(32, config["signal"], config["channel"], {"enabled": False}, 2026,
                          "ad_amr_v1_1_train", snr_values=snrs)
    old.set_epoch(4)
    new.set_epoch(4)
    for index in range(32):
        left, right = old[index], new[index]
        assert left["label"] == right["label"]
        assert left["snr_db"] == right["snr_db"]
        assert torch.equal(left["clean_iq"], right["clean_iq"])
        assert torch.equal(left["noisy_iq"], right["noisy_iq"])
        assert right["channel_profile"] == "base"


def test_curriculum_probabilities_are_normalized_and_ramp_to_target() -> None:
    config = load_yaml("configs/ad_amr_v1_2.yaml")
    dataset = ADAMRV12Dataset(
        32, config["signal"], config["channel"], config["data_robustness"],
        2026, "ad_amr_v1_2_train", snr_values=config["dataset"]["snr_values"],
    )
    start = dataset.profile_probabilities(1)
    final = dataset.profile_probabilities(30)
    assert sum(start.values()) == pytest.approx(1.0)
    assert sum(final.values()) == pytest.approx(1.0)
    assert start["base"] == pytest.approx(0.70)
    assert final == pytest.approx(config["data_robustness"]["target_weights"])
    assert final["multi_impairment"] > start["multi_impairment"]


def test_each_focus_profile_is_exercised_and_has_required_effects() -> None:
    config = load_yaml("configs/ad_amr_v1_2_smoke.yaml")
    dataset = ADAMRV12Dataset(
        512, config["signal"], config["channel"], config["data_robustness"],
        2026, "ad_amr_v1_2_train", snr_values=config["dataset"]["snr_values"],
    )
    dataset.set_epoch(30)
    seen: dict[str, tuple[str, ...]] = {}
    for index in range(len(dataset)):
        record = dataset[index]
        assert torch.isfinite(record["noisy_iq"]).all()
        seen.setdefault(record["channel_profile"], record["channel_effects"])
    assert set(seen) == set(dataset.profile_names)
    assert "cfo" in seen["cfo_focus"]
    assert "multipath" in seen["multipath_focus"]
    assert {"cfo", "phase_noise", "iq_imbalance", "multipath"}.issubset(
        set(seen["multi_impairment"])
    )


def test_training_support_is_not_an_exact_copy_of_held_out_ood() -> None:
    config = load_yaml("configs/ad_amr_v1_2.yaml")
    profiles = config["data_robustness"]["profiles"]
    held_out = ood_channels(config["channel"])
    assert max(abs(value) for value in profiles["cfo_focus"]["cfo"]["hz"]) < max(
        abs(value) for value in held_out["cfo_strong"]["cfo"]["hz"]
    )
    assert profiles["multipath_focus"]["multipath"]["max_delay"] < \
        held_out["multipath"]["multipath"]["max_delay"]
    assert profiles["multi_impairment"]["multipath"]["max_delay"] < \
        held_out["multi_impairment"]["multipath"]["max_delay"]


def test_pilot_variants_are_isolated_by_signature_and_output() -> None:
    base = load_yaml("configs/ad_amr_v1_2.yaml")
    configs = [variant_config(base, name, 2026, 30) for name in base["pilot"]["variants"]]
    assert len({config["output_root"] for config in configs}) == len(configs)
    assert len({training_signature(config) for config in configs}) == len(configs)
    assert configs[0]["data_robustness"]["enabled"] is False
    assert configs[1]["data_robustness"]["target_weights"]["multi_impairment"] == 0.0
    assert configs[2]["data_robustness"]["target_weights"]["multi_impairment"] > 0.0


def test_cpu_smoke_resume_and_unchanged_npu_graph(tmp_path: Path) -> None:
    config = copy.deepcopy(load_yaml("configs/ad_amr_v1_2_smoke.yaml"))
    config["output_root"] = str(tmp_path / "v1_2_smoke")
    config["dataset"]["train_samples"] = 210
    config["dataset"]["val_samples"] = 210
    first = run_v1_2_training(config, stop_after_epoch=1)
    assert [row["epoch"] for row in first["history"]] == [1]
    second = run_v1_2_training(config, resume=True, stop_after_epoch=1)
    assert [row["epoch"] for row in second["history"]] == [1, 2]
    checkpoint = Path(config["output_root"]) / "checkpoints/best.pt"
    report = export_v1_2(config, checkpoint)
    assert report["inspection"]["opset"] == 17
    assert report["inspection"]["unexpected_operators"] == []
    assert report["ort_parity"]["status"] == "ok"
