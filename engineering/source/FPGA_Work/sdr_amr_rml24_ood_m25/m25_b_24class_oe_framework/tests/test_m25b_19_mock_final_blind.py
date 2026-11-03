"""Mock final blind OOD evaluation: metrics at a locked threshold, no INSUFFICIENT."""
import numpy as np

from ood import m25b_metrics as mm
from ood import m25b_scores as sc
from ood import m25b_thresholds as th


def _family_logits(rng, id_peak, ood_peak, n=600, dim=24):
    # ID: confident — one randomly chosen class peaks, rest are background.
    id_logits = rng.normal(0, 1, size=(n, dim))
    id_logits[np.arange(n), rng.integers(0, dim, size=n)] += id_peak
    # OOD: flat, weakly-peaked logits (energy sits closer to -log(dim)).
    ood_logits = rng.normal(0, 1, size=(n, dim))
    ood_logits[np.arange(n), rng.integers(0, dim, size=n)] += ood_peak
    id_scores = sc.score_energy(id_logits)
    ood_scores = sc.score_energy(ood_logits)
    return id_scores, ood_scores


def test_mock_final_blind():
    rng = np.random.default_rng(0)
    id_val, far_val = _family_logits(rng, 6.0, 0.0)
    thresholds = th.select_thresholds(id_val, far_val)

    # Fresh final blind families (near and far).
    id_test, near_test = _family_logits(rng, 6.0, 3.0)
    _, far_test = _family_logits(rng, 6.0, 0.0)

    for name, ood in (("near", near_test), ("far", far_test)):
        battery = mm.evaluate_family(id_test, ood, threshold=thresholds["id_accept_99"])
        assert battery["auroc"]["result"] == "OK"
        assert battery["ood_detection_accuracy"]["result"] == "OK"
        assert 0.0 <= battery["auroc"]["value"] <= 1.0
        # far family must separate better than near in this synthetic regime
        if name == "far":
            assert battery["auroc"]["value"] > 0.9


def test_insufficient_family_flagged():
    rng = np.random.default_rng(0)
    id_scores = sc.score_energy(rng.normal(0, 1, size=(1, 24)))
    ood_scores = sc.score_energy(rng.normal(0, 1, size=(1, 24)))
    battery = mm.evaluate_family(id_scores, ood_scores, threshold=0.0)
    assert battery["auroc"]["result"] == "INSUFFICIENT"
