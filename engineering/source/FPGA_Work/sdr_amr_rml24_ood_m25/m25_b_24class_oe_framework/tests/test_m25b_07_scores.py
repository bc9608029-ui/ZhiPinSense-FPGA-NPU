"""OOD score tests: direction convention (larger = more OOD) and stability."""
import numpy as np
import pytest

from ood import m25b_scores as sc


def test_energy_of_uniform_logits():
    n = 24
    logits = np.zeros((2, n))
    e = sc.score_energy(logits, temperature=1.0)
    expected = -np.log(n)
    assert np.allclose(e, expected, atol=1e-9)


def test_msp_bounds():
    logits = np.array([[10.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    m = sc.score_msp(logits)
    assert np.all((m >= 0.0) & (m <= 1.0))


def test_confident_is_less_ood():
    confident = np.array([[8.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                           0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                           0.0, 0.0, 0.0, 0.0]])
    flat = np.zeros((1, 24))
    for name in ("msp", "entropy", "energy"):
        fn = sc.compute_score
        assert fn(flat, name)[0] > fn(confident, name)[0], name


def test_logit_margin_direction():
    confident = np.array([[8.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                           0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                           0.0, 0.0, 0.0, 0.0]])
    flat = np.zeros((1, 24))
    assert sc.score_logit_margin(flat)[0] > sc.score_logit_margin(confident)[0]


def test_max_logit_direction():
    confident = np.array([[8.0] + [0.0] * 23])
    flat = np.zeros((1, 24))
    assert sc.score_max_logit(flat)[0] > sc.score_max_logit(confident)[0]


def test_unknown_score_raises():
    with pytest.raises(ValueError):
        sc.compute_score(np.zeros((1, 24)), "bogus")


def test_energy_temperature_positive():
    with pytest.raises(ValueError):
        sc.score_energy(np.zeros((1, 24)), temperature=0.0)
