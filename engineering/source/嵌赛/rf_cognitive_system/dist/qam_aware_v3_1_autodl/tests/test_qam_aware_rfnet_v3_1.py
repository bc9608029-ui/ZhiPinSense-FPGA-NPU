import torch
import numpy as np

from deployment.numerical_contract import planned_fpga_tensors_from_int16
from models.qam_aware_rfnet_v3 import DeploymentInputEmulator
from models.qam_aware_rfnet_v3_1 import (
    HigherOrderMomentPool,
    build_qam_aware_v3_1,
    build_qam_aware_v3_1_partition,
    qam_aware_v3_1_profile,
)
from training.qam_aware_v3_1_utils import load_qam_aware_v3_1_config


def _model():
    return build_qam_aware_v3_1(
        8,
        iq_branch_channels=4,
        iq_stem_channels=12,
        physical_branch_channels=3,
        physical_stem_channels=8,
        fusion_channels=16,
        stage_channels=[16, 24, 32],
        classifier_features=24,
        dropout=0.1,
        physical_moment_order=4,
    )


def test_v3_1_output_shape_and_finite_values() -> None:
    torch.manual_seed(31)
    model = _model().eval()
    with torch.inference_mode():
        output = model(torch.randn(3, 2, 1024))
    assert output.shape == (3, 8)
    assert torch.isfinite(output).all()


def test_v3_1_external_partition_is_exact() -> None:
    torch.manual_seed(32)
    model = _model().eval()
    partition = build_qam_aware_v3_1_partition(model).eval()
    iq = torch.randn(2, 2, 1024)
    prepared_iq, physical = model.prepare_inputs(iq)
    with torch.inference_mode():
        expected = model(iq)
        actual = partition(prepared_iq, physical)
    torch.testing.assert_close(actual, expected, rtol=0.0, atol=0.0)


def test_v3_1_backpropagates_without_nonfinite_gradients() -> None:
    torch.manual_seed(33)
    model = _model().train()
    inputs = torch.randn(4, 2, 1024)
    loss = torch.nn.functional.cross_entropy(model(inputs), torch.tensor([0, 1, 2, 3]))
    loss.backward()
    assert torch.isfinite(loss)
    assert all(
        parameter.grad is None or torch.isfinite(parameter.grad).all()
        for parameter in model.parameters()
    )


def test_v3_1_profile_is_bounded_and_contract_is_preserved() -> None:
    model = _model()
    profile = qam_aware_v3_1_profile(model)
    assert 0 < profile["parameters"] < 2_000_000
    assert 0 < profile["neural_macs"] < 250_000_000
    assert "physical[N,3,1024]" in profile["input_contract"]


def test_higher_order_moment_pool_computes_exact_moments() -> None:
    torch.manual_seed(44)
    pool = HigherOrderMomentPool(order=4)
    features = torch.randn(2, 3, 16)
    output = pool(features)
    assert output.shape == (2, 12)  # 3 channels x 4 moments
    expected = torch.cat(
        [(features**k).mean(dim=-1) for k in (1, 2, 3, 4)], dim=1
    )
    torch.testing.assert_close(output, expected, rtol=1e-5, atol=1e-6)


def test_v3_1_deployment_emulator_uses_frozen_scales_and_saturation() -> None:
    emulator = DeploymentInputEmulator()
    iq = torch.tensor([[[0.0, 1.0, -1.0, 0.5], [0.0, 0.0, 0.0, -0.5]]])
    prepared_iq, physical = emulator(iq)
    assert prepared_iq.min() >= -1.0
    assert prepared_iq.max() <= 1.0
    torch.testing.assert_close(prepared_iq * 127.0, torch.round(prepared_iq * 127.0))
    torch.testing.assert_close(physical * (127.0 / 2.0), torch.round(physical * (127.0 / 2.0)))
    assert physical.shape == (1, 3, 4)


def test_v3_1_deployment_emulator_matches_frozen_integer_reference() -> None:
    iq_int16 = np.asarray(
        [[0, 0], [1, -1], [16384, -16384], [32767, -32768], [-12345, 23456]],
        dtype=np.int16,
    )
    reference = planned_fpga_tensors_from_int16(iq_int16)
    iq_ncl = torch.from_numpy(iq_int16.astype(np.float32).T / 32768.0).unsqueeze(0)
    prepared_iq, physical = DeploymentInputEmulator()(iq_ncl)
    actual_iq = torch.round(prepared_iq[0] * 127.0).to(torch.int8).numpy()
    actual_physical = torch.round(physical[0] * (127.0 / 2.0)).to(torch.int8).numpy()
    np.testing.assert_array_equal(actual_iq, reference["iq_int8"])
    np.testing.assert_array_equal(actual_physical, reference["physical_int8"])


def test_v3_1_smoke_config_keeps_frozen_class_and_frame_contract() -> None:
    config = load_qam_aware_v3_1_config("configs/qam_aware_v3_1_smoke.yaml")
    assert config["signal"]["modulations"] == [
        "BPSK",
        "QPSK",
        "8PSK",
        "16QAM",
        "64QAM",
        "2FSK",
        "CPFSK",
        "OFDM",
    ]
    assert config["signal"]["sample_length"] == 1024
    assert config["training"]["epochs"] == 2
    assert config["model"]["physical_moment_order"] == 4
    assert config["final_blind_test"]["split"] == "v3_1_final_blind_test"


def test_v3_1_config_wires_checkpoint_and_early_stop_fixes() -> None:
    config = load_qam_aware_v3_1_config("configs/qam_aware_v3_1.yaml")
    training = config["training"]
    assert training["checkpoint_metric"] == "val_macro_f1"
    assert training["checkpoint_mode"] == "max"
    assert training["minimum_epochs_before_stopping"] == 45
    assert training["class_weights"]["16QAM"] > 1.0
    assert training["class_weights"]["64QAM"] > 1.0
    # Gentle robustness: destructive fading/interference are disabled.
    assert config["channel"]["rayleigh"]["enabled"] is False
    assert config["channel"]["multipath"]["enabled"] is False
    assert config["channel"]["narrowband_interference"]["enabled"] is False
    # V2-mild impairment levels preserved.
    assert config["channel"]["cfo"]["probability"] == 0.6
