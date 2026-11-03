import numpy as np
import torch

from training.utils import set_seed


def test_global_seed_is_deterministic():
    set_seed(2026)
    first_numpy = np.random.random(5)
    first_torch = torch.rand(5)
    set_seed(2026)
    assert np.array_equal(first_numpy, np.random.random(5))
    assert torch.equal(first_torch, torch.rand(5))

