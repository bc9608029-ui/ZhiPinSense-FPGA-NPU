from pathlib import Path

import torch
import yaml

from deployment.fixed_point_frontend import power_lag1_int16
from deployment.time_power_phase_partition import TimePowerPhaseNPUPartition, external_physical_features
from models.qam_aware_rfnet import TimePowerPhaseRFNet


def _model() -> TimePowerPhaseRFNet:
    return TimePowerPhaseRFNet(
        num_classes=8,
        time_base_channels=22,
        physical_base_channels=8,
        fusion_features=64,
        dropout=0.1,
    ).eval()


def test_external_fpga_partition_is_exactly_equivalent() -> None:
    torch.manual_seed(2026)
    model = _model()
    partition = TimePowerPhaseNPUPartition(model).eval()
    iq = torch.randn(3, 2, 1024)
    physical = external_physical_features(model, iq)
    with torch.inference_mode():
        expected = model(iq)
        actual = partition(iq, physical)
    torch.testing.assert_close(actual, expected, rtol=0.0, atol=0.0)


def test_external_feature_contract_shape_dtype_and_order() -> None:
    model = _model()
    iq = torch.tensor([[[1.0, 2.0], [3.0, 4.0]]], dtype=torch.float32)
    features = external_physical_features(model, iq)
    expected = torch.tensor([[[10.0, 20.0], [0.0, 14.0], [0.0, -2.0]]])
    assert features.shape == (1, 3, 2)
    assert features.dtype == torch.float32
    torch.testing.assert_close(features, expected)


def test_machine_readable_deployment_contract() -> None:
    contract = yaml.safe_load(Path("configs/deployment_contract.yaml").read_text(encoding="utf-8"))
    assert contract["frame"]["complex_samples"] == 1024
    assert contract["fpga_features"]["channel_order"] == ["power", "lag1_real", "lag1_imag"]
    assert contract["npu_inputs"][0]["shape"] == [1, 2, 1024]
    assert contract["npu_inputs"][1]["shape"] == [1, 3, 1024]
    assert contract["npu_output"]["shape"] == [1, 8]


def test_int16_frontend_is_bit_exact_and_zero_padded() -> None:
    import numpy as np

    iq = np.asarray([[1, 3], [2, 4], [-2, 1]], dtype=np.int16)
    features = power_lag1_int16(iq)
    np.testing.assert_array_equal(features["power_u32_exact"], [10, 20, 5])
    np.testing.assert_array_equal(features["lag1_real_s33_exact"], [0, 14, 0])
    np.testing.assert_array_equal(features["lag1_imag_s33_exact"], [0, -2, 10])


def test_int16_frontend_preserves_required_guard_bits() -> None:
    import numpy as np

    iq = np.asarray([[-32768, -32768], [-32768, -32768]], dtype=np.int16)
    features = power_lag1_int16(iq)
    assert int(features["power_u32_exact"].max()) == 2**31
    assert int(features["lag1_real_s33_exact"].max()) == 2**31
    assert int(features["lag1_imag_s33_exact"][0]) == 0
