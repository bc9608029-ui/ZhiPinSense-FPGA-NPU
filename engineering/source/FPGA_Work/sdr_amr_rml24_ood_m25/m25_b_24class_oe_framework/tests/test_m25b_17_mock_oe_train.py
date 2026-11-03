"""Mock OE training step with the Energy loss and a _RecordingTrial-style object."""
import pytest

torch = pytest.importorskip("torch")

from training import m25b_oe_energy_loss as oe  # noqa: E402


class _RecordingTrial:
    """Minimal optuna-free stand-in that records suggestions and params."""

    def __init__(self):
        self.params = {}

    def suggest_float(self, name, low, high):
        value = (low + high) / 2.0
        self.params[name] = value
        return value

    def suggest_categorical(self, name, choices):
        value = choices[0]
        self.params[name] = value
        return value

    def suggest_int(self, name, low, high):
        value = low
        self.params[name] = value
        return value


def _objective(trial):
    torch.manual_seed(0)
    model = torch.nn.Linear(2048, 24)
    opt = torch.optim.SGD(model.parameters(), lr=0.01)
    temperature = trial.suggest_float("temperature", 1.0, 2.0)
    lambda_ = trial.suggest_float("lambda_oe", 0.05, 0.5)
    logits_id = model(torch.randn(16, 2048))
    labels_id = torch.randint(0, 24, (16,))
    logits_ood = model(torch.randn(16, 2048))
    loss, comps = oe.oe_energy_loss(logits_id, labels_id, logits_ood,
                                    temperature=temperature, lambda_=lambda_,
                                    margin_in=0.0, margin_out=-10.0)
    opt.zero_grad()
    loss.backward()
    opt.step()
    return loss.item(), comps


def test_mock_oe_train_step():
    trial = _RecordingTrial()
    loss, comps = _objective(trial)
    assert isinstance(loss, float)
    assert "ce" in comps
    assert "temperature" in trial.params
    assert "lambda_oe" in trial.params


def test_oe_loss_reduces_energy_gap():
    torch.manual_seed(0)
    model = torch.nn.Linear(2048, 24)
    opt = torch.optim.SGD(model.parameters(), lr=0.1)
    # Fixed batch so the model can actually overfit and pull CE + energy down.
    x_id = torch.randn(32, 2048)
    labels_id = torch.randint(0, 24, (32,))
    x_ood = torch.randn(32, 2048)
    losses = []
    for _ in range(60):
        logits_id = model(x_id)   # fresh graph, same data (no re-backprop)
        logits_ood = model(x_ood)
        loss, _ = oe.oe_energy_loss(logits_id, labels_id, logits_ood,
                                    margin_in=0.0, margin_out=-10.0, lambda_=0.5)
        opt.zero_grad()
        loss.backward()
        opt.step()
        losses.append(loss.item())
    assert losses[-1] < losses[0]
