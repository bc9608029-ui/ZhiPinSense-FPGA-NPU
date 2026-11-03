from __future__ import annotations

import onnx
import pytest
import torch

from models.dual_domain_rfnet import FixedDFTLogPower, ablation_model_profile, build_ablation_model


@pytest.mark.parametrize("variant", ["time_only", "frequency_only", "time_only_wide", "dual"])
def test_ablation_forward_shape(variant: str) -> None:
    model = build_ablation_model(variant, 8, base_channels=4, fusion_features=16, fft_length=256)
    assert model(torch.randn(3, 2, 1024)).shape == (3, 8)


def test_fixed_dft_matches_torch_fft() -> None:
    iq = torch.randn(2, 2, 1024)
    layer = FixedDFTLogPower(256)
    actual = layer(iq).squeeze(1)
    frames = torch.complex(iq[:, 0], iq[:, 1]).reshape(2, 4, 256)
    expected = torch.log1p(torch.roll(torch.fft.fft(frames).abs().square().mean(dim=1) / 256.0, 128, dims=-1))
    torch.testing.assert_close(actual, expected, rtol=2e-4, atol=2e-4)


def test_dual_profile_includes_fft_work() -> None:
    time_model = build_ablation_model("time_only", 8, base_channels=4, fusion_features=16, fft_length=256)
    dual_model = build_ablation_model("dual", 8, base_channels=4, fusion_features=16, fft_length=256)
    assert ablation_model_profile(dual_model, 1024)["approx_macs"] > ablation_model_profile(time_model, 1024)["approx_macs"]


@pytest.mark.parametrize("variant", ["time_only", "frequency_only", "time_only_wide", "dual"])
def test_onnx_export_and_checker(variant: str, tmp_path) -> None:
    model = build_ablation_model(variant, 8, base_channels=4, fusion_features=16, fft_length=256).eval()
    destination = tmp_path / f"{variant}.onnx"
    torch.onnx.export(model, torch.zeros(1, 2, 1024), destination, opset_version=17, dynamo=False)
    onnx.checker.check_model(onnx.load(destination))


def test_time_only_wide_parameter_match() -> None:
    config = dict(base_channels=16, wide_base_channels=23, fusion_features=64, fft_length=256)
    wide = sum(parameter.numel() for parameter in build_ablation_model("time_only_wide", 8, **config).parameters())
    dual = sum(parameter.numel() for parameter in build_ablation_model("dual", 8, **config).parameters())
    assert abs(wide - dual) / dual <= 0.05
