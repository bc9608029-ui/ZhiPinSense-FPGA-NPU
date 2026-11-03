"""AD-AMR model unit tests: shapes, length preservation, ECA/ERSB, budget."""

from __future__ import annotations

import torch

from models.ad_amr_net import (
    ADAMRNet,
    ADM,
    ECA,
    ERSB,
    FEM,
    build_ad_amr_model,
    eca_kernel_size,
    profile_ad_amr_model,
    soft_threshold,
)
from training.utils import load_yaml


def _config() -> dict:
    return load_yaml("configs/ad_amr_v1.yaml")


def test_model_output_shapes() -> None:
    model = build_ad_amr_model(8, **_config()["model"]).eval()
    x = torch.randn(3, 2, 1024)
    with torch.inference_mode():
        logits, denoised = model(x)
    assert tuple(logits.shape) == (3, 8)
    assert tuple(denoised.shape) == (3, 2, 1024)


def test_adm_length_preservation() -> None:
    adm = ADM(in_channels=2, base_channels=8, num_levels=3).eval()
    for length in (1024, 512, 256):
        x = torch.randn(2, 2, length)
        with torch.inference_mode():
            out = adm(x)
        assert out.shape == x.shape, f"length {length} not preserved: {tuple(out.shape)}"


def test_soft_threshold_identity_at_zero() -> None:
    x = torch.tensor([-2.0, -1.0, 0.5, 3.0])
    out = soft_threshold(x, torch.tensor(0.0))
    assert torch.allclose(out, x, atol=1e-6)


def test_soft_threshold_contracts() -> None:
    x = torch.tensor([-2.0, -0.3, 0.4, 3.0])
    threshold = torch.tensor(1.0)
    out = soft_threshold(x, threshold)
    # values within +-1 are zeroed; outside shrink by 1 toward zero.
    assert torch.allclose(out, torch.tensor([-1.0, 0.0, 0.0, 2.0]), atol=1e-6)


def test_eca_weights_shape_and_range() -> None:
    eca = ECA(channels=16).eval()
    x = torch.randn(2, 16, 64)
    with torch.inference_mode():
        weights = eca(x)
    assert tuple(weights.shape) == (2, 16, 1)
    assert bool((weights >= 0.0).all()) and bool((weights <= 1.0).all())


def test_eca_kernel_size_odd_and_min_three() -> None:
    for channels in (8, 16, 32, 64, 128):
        k = eca_kernel_size(channels)
        assert k >= 3 and k % 2 == 1


def test_ersb_stride_and_channels() -> None:
    block = ERSB(in_channels=16, out_channels=32, stride=2).eval()
    x = torch.randn(2, 16, 128)
    with torch.inference_mode():
        out = block(x)
    assert tuple(out.shape) == (2, 32, 64)


def test_fem_table_i_configuration() -> None:
    fem = FEM(in_channels=2, stem_channels=16, ersb_channels=(16, 32, 32, 64),
              strides=(2, 2, 2, 2)).eval()
    x = torch.randn(2, 2, 1024)
    with torch.inference_mode():
        out = fem(x)
    # 4 strides of 2 -> length / 16; final channels 64.
    assert tuple(out.shape) == (2, 64, 64)


def test_parameter_budget_in_paper_ballpark() -> None:
    model = build_ad_amr_model(8, **_config()["model"])
    profile = profile_ad_amr_model(model, 1024)
    params = profile["parameters"]
    assert 100_000 < params < 500_000, f"unexpected param count {params}"
    assert profile["neural_macs"] > 0
    assert profile["neural_flops"] == 2 * profile["neural_macs"]


def test_model_is_instance_of_adamrnet() -> None:
    model = build_ad_amr_model(8, **_config()["model"])
    assert isinstance(model, ADAMRNet)
