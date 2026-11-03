"""OE + Energy loss tests (torch guarded)."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from training import m25b_oe_energy_loss as oe  # noqa: E402


def test_energy_score_t_constant():
    n = 24
    logits = torch.zeros(4, n)
    e = oe.energy_score_t(logits, temperature=1.0)
    assert torch.allclose(e, torch.full((4,), -float(np.log(n))), atol=1e-5)


def test_energy_score_temperature():
    logits = torch.zeros(4, 24)
    e = oe.energy_score_t(logits, temperature=2.0)
    assert torch.allclose(e, torch.full((4,), -2.0 * float(np.log(24))), atol=1e-4)


def test_oe_energy_loss_components():
    torch.manual_seed(0)
    logits_id = torch.randn(8, 24, requires_grad=True)
    labels_id = torch.randint(0, 24, (8,))
    logits_ood = torch.randn(8, 24, requires_grad=True)
    total, comps = oe.oe_energy_loss(logits_id, labels_id, logits_ood,
                                     margin_in=0.0, margin_out=-10.0, lambda_=0.1)
    assert total.ndim == 0
    assert total.requires_grad
    assert set(comps.keys()) == {"ce", "energy_pull_id", "energy_push_ood"}
    for v in comps.values():
        assert v.ndim == 0


def test_oe_energy_loss_temperature_rejected():
    with pytest.raises(ValueError):
        oe.energy_score_t(torch.zeros(2, 24), temperature=0.0)
