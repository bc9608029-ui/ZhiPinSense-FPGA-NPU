from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pytest
import torch

from datasets.ad_amr_v1_1_dataset import (
    ADAMRV11Dataset, assert_selection_split, assert_v1_1_signal_contract,
)
from datasets.modulation_generator import V1_1_MODULATIONS, generate_iq
from models.ad_amr_v1_1_net import ADAMRV11Classifier, build_ad_amr_v1_1_model
from models.ad_amr_v1_1_teachers import OLD_CLASSES, TeacherEnsemble
from scripts.export_ad_amr_v1_1_onnx import ALLOWED_OPS, export_v1_1
from training.ad_amr_v1_1_loss import TEACHER_TO_STUDENT, ad_amr_v1_1_loss, snr_weights
from training.train_ad_amr_v1_1 import run_v1_1_training
from training.utils import load_yaml


def test_fixed_ten_class_contract_and_generators_are_finite() -> None:
    config = load_yaml("configs/ad_amr_v1_1.yaml")
    assert tuple(config["signal"]["modulations"]) == V1_1_MODULATIONS
    for index, name in enumerate(V1_1_MODULATIONS):
        first, _ = generate_iq(name, config["signal"], np.random.default_rng(index))
        second, _ = generate_iq(name, config["signal"], np.random.default_rng(index))
        assert first.shape == (1024,)
        assert np.isfinite(first).all()
        assert np.array_equal(first, second)
        assert np.isclose(np.mean(np.abs(first) ** 2), 1.0, atol=1e-4)


def test_dataset_balances_class_and_snr_and_isolates_splits() -> None:
    config = load_yaml("configs/ad_amr_v1_1_smoke.yaml")
    count = len(V1_1_MODULATIONS) * len(config["dataset"]["snr_values"])
    train = ADAMRV11Dataset(count, config["signal"], config["channel"], 2026,
                            "ad_amr_v1_1_train", snr_values=config["dataset"]["snr_values"])
    validation = ADAMRV11Dataset(count, config["signal"], config["channel"], 2026,
                                 "ad_amr_v1_1_validation", snr_values=config["dataset"]["snr_values"])
    assert {train[i]["label"] for i in range(count)} == set(range(10))
    assert {train[i]["snr_db"] for i in range(count)} == set(config["dataset"]["snr_values"])
    assert {train[i]["sample_id"] for i in range(count)}.isdisjoint(
        {validation[i]["sample_id"] for i in range(count)}
    )
    with pytest.raises(RuntimeError):
        ADAMRV11Dataset(10, config["signal"], config["channel"], split="final_blind")
    with pytest.raises(RuntimeError):
        assert_selection_split("test")


def test_wrong_class_order_is_rejected() -> None:
    config = copy.deepcopy(load_yaml("configs/ad_amr_v1_1.yaml")["signal"])
    config["modulations"] = list(reversed(config["modulations"]))
    with pytest.raises(ValueError):
        assert_v1_1_signal_contract(config)


def test_student_shapes_gradients_and_deploy_modules() -> None:
    config = load_yaml("configs/ad_amr_v1_1.yaml")
    model = build_ad_amr_v1_1_model(10, **config["model"])
    inputs = torch.randn(4, 2, 1024)
    logits, denoised = model(inputs)
    assert logits.shape == (4, 10)
    assert denoised.shape == inputs.shape
    logits.sum().backward()
    assert all(parameter.grad is not None and torch.isfinite(parameter.grad).all()
               for parameter in model.parameters())
    forbidden_types = (torch.nn.Sigmoid, torch.nn.Upsample, torch.nn.ConvTranspose1d)
    assert not any(isinstance(module, forbidden_types) for module in model.modules())
    assert ADAMRV11Classifier(model)(inputs).shape == (4, 10)


def test_loss_snr_weighting_and_teacher_projection() -> None:
    config = load_yaml("configs/ad_amr_v1_1.yaml")
    logits = torch.randn(10, 10, requires_grad=True)
    clean = torch.randn(10, 2, 64)
    denoised = torch.randn(10, 2, 64, requires_grad=True)
    labels = torch.arange(10)
    snrs = torch.tensor([-20, -12, -10, -4, 0, 2, 4, 8, 12, 20], dtype=torch.float32)
    weights = snr_weights(snrs, config["training"]["snr_weighting"])
    assert weights[0] < weights[2] < weights[4]
    assert len(TEACHER_TO_STUDENT) == len(OLD_CLASSES) == 8
    loss, components = ad_amr_v1_1_loss(
        logits, denoised, clean, labels, snrs, config["training"], teachers=None,
    )
    loss.backward()
    assert torch.isfinite(loss)
    assert set(components) == {"ce", "reconstruction", "total"}


def test_frozen_teacher_ensemble_loads_and_stays_frozen() -> None:
    config = load_yaml("configs/ad_amr_v1_1.yaml")
    teachers = TeacherEnsemble(config, torch.device("cpu"))
    v2, v1 = teachers.logits(torch.randn(2, 2, 1024))
    assert v2.shape == v1.shape == (2, 8)
    modules = [teachers.v2, *teachers.v1]
    assert all(not parameter.requires_grad for module in modules for parameter in module.parameters())


def test_cpu_smoke_resume_and_strict_onnx_gate(tmp_path: Path) -> None:
    config = load_yaml("configs/ad_amr_v1_1_smoke.yaml")
    config["output_root"] = str(tmp_path / "smoke")
    config["dataset"]["train_samples"] = 210
    config["dataset"]["val_samples"] = 210
    first = run_v1_1_training(config, stop_after_epoch=1)
    assert [row["epoch"] for row in first["history"]] == [1]
    second = run_v1_1_training(config, resume=True, stop_after_epoch=1)
    assert [row["epoch"] for row in second["history"]] == [1, 2]
    checkpoint = Path(config["output_root"]) / "checkpoints/best.pt"
    report = export_v1_1(config, checkpoint)
    assert report["inspection"]["opset"] == 17
    assert report["inspection"]["unexpected_operators"] == []
    assert set(report["inspection"]["op_types"]).issubset(ALLOWED_OPS)
    assert report["ort_parity"]["status"] == "ok"
