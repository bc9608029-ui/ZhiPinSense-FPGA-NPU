"""M20 test category 13: known-class protection (OOD-R not rejected).

Impaired 12-class signals (CFO / phase noise / IQ imbalance / multipath /
clipping / multi / strong-nearby) are *known* signals under channel impairment;
the OOD-U detector must still accept them, not reject them as UNKNOWN.  The
frozen threshold is derived from a deterministic mini-calibration on the
ood_validation split, and the low-SNR (-20/-10 dB) regime is asserted to be
excluded from that calibration domain (so it can never inflate the OOD metric).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ood_u import contract
from ood_u.benchmark import run_score_benchmark
from ood_u.calibrate import calibrate, select_method
from ood_u.data import generate_id_split, generate_ood_split
from ood_u.model import load_model
from ood_u.protection import generate_protection_records, run_protection_suite

_PROJECT = Path(__file__).resolve().parents[1]

# Match the production calibration defaults (scripts/m20_threshold_calibration.py
# --count-per-class/--count-per-modulation 20).  Smaller counts make select_method
# pick a different score method (e.g. msp at 12) and produce a non-representative
# threshold, so the fixture must use the same count as the frozen calibration.
_COUNT = 20


@pytest.fixture(scope="session")
def calibration():
    model = load_model(_PROJECT / "model_12class/seed2026_best.pt")
    snr = tuple(contract.BENCHMARK_SNR_VALUES)
    id_val = generate_id_split("ood_validation", seed=contract.OOD_SEED, count_per_class=_COUNT, snr_values=snr)
    near_val = generate_ood_split("near_12", "ood_validation", seed=contract.OOD_SEED, count_per_modulation=_COUNT, snr_values=snr)
    far_val = generate_ood_split("far", "ood_validation", seed=contract.OOD_SEED, count_per_modulation=_COUNT, snr_values=snr)
    amb_val = generate_ood_split("ambiguous", "ood_validation", seed=contract.OOD_SEED, count_per_modulation=_COUNT, snr_values=snr)
    impaired = generate_protection_records("clean", "ood_validation", seed=contract.OOD_SEED, count_per_class=_COUNT)
    bench = run_score_benchmark(model, id_val, near_val, far_val, amb_val, impaired)
    method, _ = select_method(bench)
    result = calibrate(model, id_val, near_val, far_val, chosen_method=method)
    return model, result["score_method"], result["temperature"], result["threshold"]


def test_ood_r_known_classes_not_rejected(calibration):
    model, method, temperature, threshold = calibration
    report = run_protection_suite(
        model, score_method=method, temperature=temperature, threshold=threshold,
        split="ood_final_test", seed=contract.OOD_SEED, count_per_class=_COUNT,
    )

    # Clean known class at 10 dB is accepted essentially always.
    assert report["clean"]["id_accept_rate"] >= 0.95, report["clean"]

    # Every impaired known class (excluding the low-SNR sweep) stays accepted.
    for cond in ("cfo", "phase_noise", "iq_imbalance", "multipath",
                 "clipping", "multi", "strong_nearby"):
        accept = report[cond]["id_accept_rate"]
        assert accept >= 0.85, f"{cond} accept {accept}"

    # 0 dB known class is still accepted (the calibration domain starts at 0 dB).
    per_snr = report["snr_sweep"]["per_snr_reject_rate"]
    assert per_snr["0"] <= 0.10, per_snr
    # Low-SNR known classes are not systematically 100%-rejected (no mass reject).
    assert per_snr["-10"] < 0.90, per_snr
    assert per_snr["-20"] < 0.90, per_snr

    # The calibration domain never includes the low-SNR regime.
    assert tuple(contract.BENCHMARK_SNR_VALUES) == (0.0, 10.0, 20.0)
