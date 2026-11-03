"""NPU-boundary tests (lazy torch/ort; numpy-only checks always run)."""
import numpy as np
import pytest

from npu_boundary import m25b_npu_boundary as nb


def test_fake_int8_bounded():
    logits = np.random.default_rng(0).normal(0, 5, size=(4, 24))
    q = nb.fake_int8_logits(logits)
    assert q.shape == logits.shape
    assert np.all(np.abs(q) <= np.max(np.abs(logits)) + 1e-9)


def test_compare_logits_same():
    a = np.random.default_rng(0).normal(size=(4, 24))
    r = nb.compare_logits(a, a.copy())
    assert r["match"] is True
    assert r["same_argmax"] is True


def test_compare_logits_diff():
    a = np.random.default_rng(0).normal(size=(4, 24))
    b = a + 1.0
    r = nb.compare_logits(a, b)
    assert r["match"] is False


def test_energy_direction_consistent():
    a = np.random.default_rng(0).normal(size=(8, 24))
    b = a + 0.001  # tiny perturbation keeps rank
    r = nb.energy_direction_consistent(a, b)
    assert r["consistent"] is True


def test_report_flags_missing_npu():
    a = np.random.default_rng(0).normal(size=(4, 24))
    report = nb.npu_boundary_report(torch_logits_arr=a, fake_int8_arr=a)
    assert report["npu_logits_missing"] is True
    assert report["npu_note"] == nb.NPU_LOGITS_MISSING


def test_energy_np_uses_scores():
    n = 24
    e = nb.energy_np(np.zeros((2, n)))
    assert np.allclose(e, -np.log(n), atol=1e-9)
