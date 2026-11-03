import torch
import numpy as np

from deployment.numerical_contract import planned_fpga_tensors_from_int16
from models.qam_aware_rfnet_v3 import (
    DeploymentInputEmulator,
    build_qam_aware_v3,
    build_qam_aware_v3_partition,
    qam_aware_v3_profile,
)
from training.qam_aware_v3_utils import load_qam_aware_v3_config


def _model():
    return build_qam_aware_v3(
        8,
        iq_branch_channels=4,
        iq_stem_channels=12,
        physical_branch_channels=3,
        physical_stem_channels=8,
        fusion_channels=16,
        stage_channels=[16, 24, 32],
        classifier_features=24,
        dropout=0.1,
    )


def test_v3_output_shape_and_finite_values() -> None:
    torch.manual_seed(31)
    model = _model().eval()
    with torch.inference_mode():
        output = model(torch.randn(3, 2, 1024))
    assert output.shape == (3, 8)
    assert torch.isfinite(output).all()


def test_v3_external_partition_is_exact() -> None:
    torch.manual_seed(32)
    model = _model().eval()
    partition = build_qam_aware_v3_partition(model).eval()
    iq = torch.randn(2, 2, 1024)
    prepared_iq, physical = model.prepare_inputs(iq)
    with torch.inference_mode():
        expected = model(iq)
        actual = partition(prepared_iq, physical)
    torch.testing.assert_close(actual, expected, rtol=0.0, atol=0.0)


def test_v3_backpropagates_without_nonfinite_gradients() -> None:
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


def test_v3_profile_is_bounded_and_contract_is_preserved() -> None:
    model = _model()
    profile = qam_aware_v3_profile(model)
    assert 0 < profile["parameters"] < 2_000_000
    assert 0 < profile["neural_macs"] < 250_000_000
    assert "physical[N,3,1024]" in profile["input_contract"]


def test_v3_deployment_emulator_uses_frozen_scales_and_saturation() -> None:
    emulator = DeploymentInputEmulator()
    iq = torch.tensor([[[0.0, 1.0, -1.0, 0.5], [0.0, 0.0, 0.0, -0.5]]])
    prepared_iq, physical = emulator(iq)
    assert prepared_iq.min() >= -1.0
    assert prepared_iq.max() <= 1.0
    torch.testing.assert_close(prepared_iq * 127.0, torch.round(prepared_iq * 127.0))
    torch.testing.assert_close(physical * (127.0 / 2.0), torch.round(physical * (127.0 / 2.0)))
    assert physical.shape == (1, 3, 4)


def test_v3_deployment_emulator_matches_frozen_integer_reference() -> None:
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


def test_v3_smoke_config_keeps_frozen_class_and_frame_contract() -> None:
    config = load_qam_aware_v3_config("configs/qam_aware_v3_smoke.yaml")
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
    assert config["final_blind_test"]["split"] == "v3_final_blind_test"
