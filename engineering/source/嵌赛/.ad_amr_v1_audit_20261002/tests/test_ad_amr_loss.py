"""P0/P1 loss-variant tests: identical except the MSE target."""

from __future__ import annotations

import torch

from models.ad_amr_net import build_ad_amr_model
from training.ad_amr_loss import ad_amr_loss
from training.utils import load_yaml, set_seed


def _make_batch(seed: int = 2026) -> dict[str, torch.Tensor]:
    set_seed(seed, deterministic=False)
    model = build_ad_amr_model(8, **load_yaml("configs/ad_amr_v1.yaml")["model"]).eval()
    clean = torch.randn(4, 2, 1024)
    noisy = clean + 0.5 * torch.randn(4, 2, 1024)
    labels = torch.randint(0, 8, (4,))
    with torch.inference_mode():
        logits, denoised = model(noisy)
    return {"model": model, "logits": logits, "denoised": denoised, "clean": clean,
            "noisy": noisy, "labels": labels}


def test_p0_p1_identical_init() -> None:
    set_seed(2026, deterministic=False)
    model_a = build_ad_amr_model(8, **load_yaml("configs/ad_amr_v1.yaml")["model"])
    set_seed(2026, deterministic=False)
    model_b = build_ad_amr_model(8, **load_yaml("configs/ad_amr_v1.yaml")["model"])
    for pa, pb in zip(model_a.state_dict().values(), model_b.state_dict().values()):
        assert torch.equal(pa, pb), "P0/P1 models must share identical initialization"


def test_p0_p1_differ_only_in_mse_target() -> None:
    b = _make_batch()
    loss_p0, comp_p0 = ad_amr_loss(b["logits"], b["denoised"], b["labels"], b["clean"],
                                   b["noisy"], "P0", 0.1)
    loss_p1, comp_p1 = ad_amr_loss(b["logits"], b["denoised"], b["labels"], b["clean"],
                                   b["noisy"], "P1", 0.1)

    # CE component is identical (same logits/labels).
    assert torch.allclose(comp_p0["ce"], comp_p1["ce"], atol=1e-6)
    # MSE target differs (noisy != clean), so the MSE and total differ.
    assert not torch.allclose(comp_p0["mse"], comp_p1["mse"])
    assert not torch.allclose(loss_p0, loss_p1)


def test_loss_decomposition_and_alpha() -> None:
    b = _make_batch()
    loss, comp = ad_amr_loss(b["logits"], b["denoised"], b["labels"], b["clean"], b["noisy"], "P0", 0.1)
    expected = comp["ce"] + 0.1 * comp["mse"]
    assert torch.allclose(loss, expected, atol=1e-6)
    # MSE target for P0 is the noisy input; for P1 the clean input.
    _, comp_p0 = ad_amr_loss(b["logits"], b["denoised"], b["labels"], b["clean"], b["noisy"], "P0", 0.1)
    _, comp_p1 = ad_amr_loss(b["logits"], b["denoised"], b["labels"], b["clean"], b["noisy"], "P1", 0.1)
    assert torch.allclose(comp_p0["mse"], ((b["denoised"] - b["noisy"]) ** 2).mean(), atol=1e-6)
    assert torch.allclose(comp_p1["mse"], ((b["denoised"] - b["clean"]) ** 2).mean(), atol=1e-6)


def test_unknown_variant_raises() -> None:
    b = _make_batch()
    try:
        ad_amr_loss(b["logits"], b["denoised"], b["labels"], b["clean"], b["noisy"], "P2", 0.1)
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown loss variant")
