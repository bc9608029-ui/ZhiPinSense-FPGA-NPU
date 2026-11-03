"""Model-level checks for V3.2: frozen-V2 preservation + zero-gated delta branch."""

from __future__ import annotations

import functools

import torch

from models.qam_aware_rfnet import build_qam_aware_model
from models.qam_aware_rfnet_v3_1 import HigherOrderMomentPool
from models.qam_aware_rfnet_v3_2 import (
    build_qam_aware_v3_2,
    build_qam_aware_v3_2_partition,
    load_v2_into_v3_2,
    qam_aware_v3_2_profile,
)
from training.qam_aware_v3_2_utils import load_qam_aware_v3_2_config

V2_CHECKPOINT = "init/v2_time_power_phase_best.pt"


@functools.lru_cache(maxsize=1)
def _v2_checkpoint() -> dict:
    return torch.load(V2_CHECKPOINT, map_location="cpu", weights_only=False)


@functools.lru_cache(maxsize=1)
def _v2_model() -> torch.nn.Module:
    checkpoint = _v2_checkpoint()
    qam_aware = checkpoint["config"]["qam_aware"]
    model = build_qam_aware_model(variant="time_power_phase", num_classes=8, **qam_aware)
    model.load_state_dict(checkpoint["model_state"], strict=True)
    return model.eval()


def _loaded_v32() -> torch.nn.Module:
    model = build_qam_aware_v3_2(8)
    load_v2_into_v3_2(model, _v2_checkpoint())
    return model


def test_v3_2_output_shape_and_finite_values() -> None:
    torch.manual_seed(1)
    model = _loaded_v32().eval()
    with torch.inference_mode():
        output = model(torch.randn(3, 2, 1024))
    assert output.shape == (3, 8)
    assert torch.isfinite(output).all()


def test_v3_2_partition_is_exactly_the_training_core() -> None:
    model = _loaded_v32().eval()
    partition = build_qam_aware_v3_2_partition(model)
    assert partition is model.core
    iq = torch.randn(2, 2, 1024)
    prepared_iq, physical = model.prepare_inputs(iq)
    with torch.inference_mode():
        expected = model(iq)
        actual = partition(prepared_iq, physical)
    torch.testing.assert_close(actual, expected, rtol=0.0, atol=0.0)


def test_v3_2_initial_logits_equal_v2_elementwise() -> None:
    model = _loaded_v32().eval()
    reference = _v2_model()
    assert float(model.core.gate.item()) == 0.0
    torch.manual_seed(2)
    iq = torch.randn(4, 2, 1024)
    with torch.inference_mode():
        student = model(iq)
        teacher = reference(iq)
    torch.testing.assert_close(student, teacher, rtol=0.0, atol=1e-5)


def test_v3_2_gate_has_nonzero_finite_gradient_at_init() -> None:
    torch.manual_seed(3)
    model = _loaded_v32().train()
    inputs = torch.randn(4, 2, 1024)
    labels = torch.tensor([0, 1, 2, 3])
    loss = torch.nn.functional.cross_entropy(model(inputs), labels)
    loss.backward()
    grad = model.core.gate.grad
    assert grad is not None
    assert torch.isfinite(grad)
    assert grad.abs().item() > 0.0


def test_v3_2_delta_branch_has_nonzero_finite_gradient_when_gate_nonzero() -> None:
    torch.manual_seed(4)
    model = _loaded_v32().train()
    model.core.gate.data.fill_(1.0)  # open the gate so the delta head receives gradient
    inputs = torch.randn(4, 2, 1024)
    labels = torch.tensor([0, 1, 2, 3])
    loss = torch.nn.functional.cross_entropy(model(inputs), labels)
    loss.backward()
    final_bias_grad = model.core.delta_head[2].bias.grad
    assert final_bias_grad is not None
    assert torch.isfinite(final_bias_grad).all()
    assert final_bias_grad.abs().sum().item() > 0.0


def test_v3_2_higher_order_moment_pool_computes_exact_moments() -> None:
    torch.manual_seed(5)
    pool = HigherOrderMomentPool(order=4)
    features = torch.randn(2, 3, 16)
    output = pool(features)
    assert output.shape == (2, 12)
    expected = torch.cat([(features**k).mean(dim=-1) for k in (1, 2, 3, 4)], dim=1)
    torch.testing.assert_close(output, expected, rtol=1e-5, atol=1e-6)


def test_v3_2_backpropagates_without_nonfinite_gradients() -> None:
    torch.manual_seed(6)
    model = _loaded_v32().train()
    model.core.gate.data.fill_(0.5)
    inputs = torch.randn(4, 2, 1024)
    loss = torch.nn.functional.cross_entropy(model(inputs), torch.tensor([0, 1, 2, 3]))
    loss.backward()
    assert torch.isfinite(loss)
    assert all(
        parameter.grad is None or torch.isfinite(parameter.grad).all()
        for parameter in model.parameters()
    )


def test_v3_2_profile_is_bounded_and_contract_is_preserved() -> None:
    model = _loaded_v32()
    profile = qam_aware_v3_2_profile(model)
    assert 0 < profile["parameters"] < 200_000
    assert 0 < profile["neural_macs"] < 20_000_000
    assert "physical[N,3,1024]" in profile["input_contract"]
    assert "iq[N,2,1024]" in profile["input_contract"]


def test_v3_2_smoke_config_keeps_frozen_class_and_frame_contract() -> None:
    config = load_qam_aware_v3_2_config("configs/qam_aware_v3_2_smoke.yaml")
    assert config["signal"]["modulations"] == [
        "BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM",
    ]
    assert config["signal"]["sample_length"] == 1024
    assert config["model_contract"]["physical_channels"] == 3
    assert config["model"]["simulate_hardware_inputs"] is False
    assert config["final_blind_test"]["split"] == "v3_2_final_blind_test"


def test_v3_2_config_wires_distillation_and_no_qam_reweighting() -> None:
    config = load_qam_aware_v3_2_config("configs/qam_aware_v3_2.yaml")
    training = config["training"]
    assert training["distillation"]["enabled"] is True
    assert training["distillation"]["temperature"] == 4.0
    assert training["distillation"]["alpha"] == 0.7
    assert training["checkpoint_metric"] == "val_macro_f1"
    assert training["checkpoint_mode"] == "max"
    assert training["minimum_epochs_before_stopping"] < training["epochs"]
    # No QAM reweighting of the base classifier — the V3.1 failure mode.
    assert training["class_weights"]["16QAM"] == 1.0
    assert training["class_weights"]["64QAM"] == 1.0
    # Full precision, exactly like frozen V2.
    assert config["model"]["simulate_hardware_inputs"] is False
