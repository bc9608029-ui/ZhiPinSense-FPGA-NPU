from __future__ import annotations

import numpy as np
import onnx
import pandas as pd
import pytest
import torch

from models.qam_aware_rfnet import (
    InstantaneousPower,
    LagOneCorrelation,
    StatisticalPooling1D,
    build_qam_aware_model,
)
from evaluation.evaluate_qam_aware import _qam_metrics
from evaluation.compare_qam_v2 import _paired_result
from evaluation.evaluate_qam_formal import _per_class_metrics


VARIANTS = ("time_power", "time_phase", "time_power_phase")


def test_qam_metrics_accepts_prediction_lists() -> None:
    classes = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]
    result = _qam_metrics([3, 3, 4, 4], [3, 4, 3, 4], classes)
    assert result["16qam_accuracy"] == 0.5
    assert result["64qam_accuracy"] == 0.5
    assert result["16qam_to_64qam_count"] == 1
    assert result["64qam_to_16qam_count"] == 1


def test_formal_per_class_metrics_and_paired_test() -> None:
    frame = _per_class_metrics(
        np.asarray([0, 0, 1, 1]), np.asarray([0, 1, 1, 1]), ["A", "B"]
    )
    assert frame.loc[0, "accuracy"] == 0.5
    assert frame.loc[1, "accuracy"] == 1.0
    reference = pd.DataFrame({"true_label": [0, 0, 1, 1], "predicted_label": [0, 1, 1, 0]})
    candidate = pd.DataFrame({"true_label": [0, 0, 1, 1], "predicted_label": [0, 0, 1, 1]})
    result = _paired_result(reference, candidate, np.ones(4, dtype=bool))
    assert result["reference_only_correct"] == 0
    assert result["candidate_only_correct"] == 2


def test_instantaneous_power_matches_numpy() -> None:
    rng = np.random.default_rng(73)
    iq_numpy = rng.normal(size=(3, 2, 19)).astype(np.float32)
    actual = InstantaneousPower()(torch.from_numpy(iq_numpy)).numpy()
    expected = iq_numpy[:, 0:1] ** 2 + iq_numpy[:, 1:2] ** 2
    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-7)


def test_lag_one_correlation_matches_numpy_and_zero_padding() -> None:
    rng = np.random.default_rng(91)
    iq_numpy = rng.normal(size=(2, 2, 23)).astype(np.float32)
    actual = LagOneCorrelation()(torch.from_numpy(iq_numpy)).numpy()
    complex_iq = iq_numpy[:, 0] + 1j * iq_numpy[:, 1]
    expected_complex = complex_iq[:, 1:] * np.conj(complex_iq[:, :-1])
    expected = np.zeros((2, 2, 23), dtype=np.float32)
    expected[:, 0, 1:] = expected_complex.real
    expected[:, 1, 1:] = expected_complex.imag
    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-6)
    assert np.count_nonzero(actual[:, :, 0]) == 0


def test_statistical_pooling_mean_and_second_moment() -> None:
    values = torch.tensor([[[1.0, 2.0, 3.0], [-1.0, 1.0, 3.0]]])
    actual = StatisticalPooling1D()(values)
    expected = torch.cat((values.mean(-1), (values * values).mean(-1)), dim=1)
    torch.testing.assert_close(actual, expected)


@pytest.mark.parametrize("variant", VARIANTS)
def test_qam_model_shape_dtype_finite_and_deterministic(variant: str) -> None:
    torch.manual_seed(8)
    model = build_qam_aware_model(
        variant, 8, time_base_channels=4, physical_base_channels=3, fusion_features=12, dropout=0.0
    ).eval()
    inputs = torch.randn(3, 2, 128, dtype=torch.float32)
    first = model(inputs)
    second = model(inputs.clone())
    assert first.shape == (3, 8)
    assert first.dtype == torch.float32
    assert torch.isfinite(first).all()
    torch.testing.assert_close(first, second, rtol=0, atol=0)


@pytest.mark.parametrize("variant", VARIANTS)
def test_qam_model_backward(variant: str) -> None:
    model = build_qam_aware_model(
        variant, 8, time_base_channels=4, physical_base_channels=3, fusion_features=12, dropout=0.0
    )
    inputs = torch.randn(4, 2, 128, requires_grad=True)
    loss = model(inputs).square().mean()
    loss.backward()
    assert inputs.grad is not None and torch.isfinite(inputs.grad).all()
    assert any(parameter.grad is not None for parameter in model.parameters() if parameter.requires_grad)


@pytest.mark.parametrize("variant", VARIANTS)
def test_qam_model_parameter_budget(variant: str) -> None:
    model = build_qam_aware_model(
        variant, 8, time_base_channels=22, physical_base_channels=8, fusion_features=64, dropout=0.1
    )
    parameters = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    assert 65_000 <= parameters <= 90_000
    assert abs(parameters - 71_148) / 71_148 <= 0.02


@pytest.mark.parametrize("variant", VARIANTS)
def test_qam_model_onnx_opset17(variant: str, tmp_path) -> None:
    model = build_qam_aware_model(
        variant, 8, time_base_channels=4, physical_base_channels=3, fusion_features=12, dropout=0.0
    ).eval()
    destination = tmp_path / f"{variant}.onnx"
    torch.onnx.export(model, torch.zeros(1, 2, 128), destination, opset_version=17, dynamo=False)
    graph = onnx.load(destination)
    onnx.checker.check_model(graph)
    op_types = {node.op_type for node in graph.graph.node}
    assert "Conv" in op_types and "Mul" in op_types and "ReduceMean" in op_types


@pytest.mark.parametrize("variant", VARIANTS)
def test_qam_model_checkpoint_save_load(variant: str, tmp_path) -> None:
    config = dict(time_base_channels=4, physical_base_channels=3, fusion_features=12, dropout=0.0)
    model = build_qam_aware_model(variant, 8, **config).eval()
    inputs = torch.randn(2, 2, 128)
    expected = model(inputs)
    checkpoint = tmp_path / "checkpoint.pt"
    torch.save({"model_state": model.state_dict(), "epoch": 2}, checkpoint)
    restored = build_qam_aware_model(variant, 8, **config).eval()
    restored.load_state_dict(torch.load(checkpoint, weights_only=False)["model_state"])
    torch.testing.assert_close(restored(inputs), expected, rtol=0, atol=0)
