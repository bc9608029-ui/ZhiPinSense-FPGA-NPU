"""Mock 24-class model end-to-end flow: raw logits -> Energy -> threshold -> OOD."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from ood import m25b_metrics as mm      # noqa: E402
from ood import m25b_scores as sc       # noqa: E402
from ood import m25b_thresholds as th   # noqa: E402


def _logits(model, x):
    with torch.no_grad():
        return model(torch.as_tensor(x, dtype=torch.float32)).detach().cpu().numpy()


def test_mock_end_to_end():
    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    # Flat mock "backbone" so the flow is exercised, not the classification quality.
    model = torch.nn.Linear(2048, 24)

    # Synthetic validation inputs (flattened 2x1024).
    id_val = rng.normal(0, 1, size=(400, 2048)).astype(np.float32)
    far_val = rng.normal(0.5, 1, size=(400, 2048)).astype(np.float32)

    id_logits = _logits(model, id_val)
    far_logits = _logits(model, far_val)

    id_energy = sc.score_energy(id_logits)
    far_energy = sc.score_energy(far_logits)

    thresholds = th.select_thresholds(id_energy, far_energy)
    assert "id_accept_99" in thresholds

    # Final blind split: apply the locked threshold.
    id_test = rng.normal(0, 1, size=(300, 2048)).astype(np.float32)
    far_test = rng.normal(0.5, 1, size=(300, 2048)).astype(np.float32)
    id_energy_test = sc.score_energy(_logits(model, id_test))
    far_energy_test = sc.score_energy(_logits(model, far_test))

    acc = mm.ood_detection_accuracy(id_energy_test, far_energy_test,
                                    thresholds["id_accept_99"])
    assert 0.0 <= acc <= 1.0


def test_raw_logits_no_softmax():
    torch.manual_seed(1)
    model = torch.nn.Linear(2048, 24)
    x = np.random.default_rng(2).normal(size=(1, 2048)).astype(np.float32)
    logits = _logits(model, x)
    assert logits.shape == (1, 24)
    # Raw logits: not probabilities (may be negative, sum != 1).
    assert not np.isclose(logits.sum(), 1.0)
