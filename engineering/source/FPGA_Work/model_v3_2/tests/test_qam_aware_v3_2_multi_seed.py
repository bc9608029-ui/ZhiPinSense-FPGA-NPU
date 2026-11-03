"""The three-seed promotion gate: mean improvement + per-seed regression floors."""

from __future__ import annotations

import functools
import math

import yaml

from evaluation.check_qam_aware_v3_2_multi_seed_acceptance import apply_multi_seed_rule, summarize
from training.utils import resolve_project_path


@functools.lru_cache(maxsize=1)
def _gate_config() -> dict:
    return yaml.safe_load(resolve_project_path("configs/qam_aware_v3_2_acceptance.yaml").read_text(encoding="utf-8"))


def _v2() -> dict:
    return _gate_config()["v2"]


def _gates() -> dict:
    return _gate_config()["promotion_gates"]


def _record(
    seed: int,
    *,
    acc_gain: float = 0.03,
    f1_gain: float = 0.03,
    qam_gain: float = 0.06,
    per_class_drop: float = 0.0,
    snr_drop: float = 0.0,
) -> dict:
    v2 = _v2()
    return {
        "seed": str(seed),
        "accuracy": float(v2["accuracy"]) + acc_gain,
        "macro_f1": float(v2["macro_f1"]) + f1_gain,
        "qam_mean_accuracy": float(v2["qam_mean_accuracy"]) + qam_gain,
        "per_class_accuracy": {name: float(value) - per_class_drop for name, value in v2["per_class_accuracy"].items()},
        "snr_accuracy": {key: float(value) - snr_drop for key, value in v2["snr_accuracy"].items()},
    }


def test_pass_when_mean_clears_and_every_seed_clears_floors() -> None:
    records = [_record(2026), _record(2027), _record(2028)]
    result = apply_multi_seed_rule(records, _v2(), _gates())
    assert result["passed"] is True
    assert result["improvement_on"] == "mean"
    assert result["regression_floors_on"] == "every_seed"


def test_fail_when_one_seed_regresses_a_class() -> None:
    records = [_record(2026), _record(2027), _record(2028)]
    # Seed 2027 regresses BPSK by 0.04 > 0.03 even though the mean is healthy.
    records[1]["per_class_accuracy"]["BPSK"] = float(_v2()["per_class_accuracy"]["BPSK"]) - 0.04
    result = apply_multi_seed_rule(records, _v2(), _gates())
    assert result["passed"] is False
    assert result["checks"]["seed2027_per_class_BPSK"] is False


def test_fail_when_one_seed_regresses_a_key_snr() -> None:
    records = [_record(2026), _record(2027), _record(2028)]
    records[2]["snr_accuracy"]["10"] = float(_v2()["snr_accuracy"]["10"]) - 0.02  # > 0.01
    result = apply_multi_seed_rule(records, _v2(), _gates())
    assert result["passed"] is False
    assert result["checks"]["seed2028_snr_10"] is False


def test_fail_when_mean_below_improvement_gate() -> None:
    # Every seed clears the floors, but the mean improvement is too small.
    records = [_record(2026, acc_gain=0.01, f1_gain=0.01, qam_gain=0.01) for _ in range(3)]
    result = apply_multi_seed_rule(records, _v2(), _gates())
    assert result["passed"] is False
    assert result["checks"]["mean_accuracy_gain"] is False


def test_no_cherry_pick_best_seed() -> None:
    # One seed alone would clear the accuracy bar; the mean of all three must not.
    records = [
        _record(2026, acc_gain=0.05, f1_gain=0.05, qam_gain=0.08),
        _record(2027, acc_gain=-0.01, f1_gain=-0.01, qam_gain=-0.01, per_class_drop=0.01),
        _record(2028, acc_gain=-0.01, f1_gain=-0.01, qam_gain=-0.01, per_class_drop=0.01),
    ]
    result = apply_multi_seed_rule(records, _v2(), _gates())
    assert result["passed"] is False
    assert result["checks"]["mean_accuracy_gain"] is False


def test_per_seed_floors_cover_every_seed_and_every_class() -> None:
    records = [_record(2026), _record(2027), _record(2028)]
    result = apply_multi_seed_rule(records, _v2(), _gates())
    for seed in (2026, 2027, 2028):
        for name in _v2()["per_class_accuracy"]:
            assert f"seed{seed}_per_class_{name}" in result["checks"]
        for key in _v2()["snr_accuracy"]:
            assert f"seed{seed}_snr_{key}" in result["checks"]


def test_summarize_mean_and_std() -> None:
    records = [_record(2026, acc_gain=0.01), _record(2027, acc_gain=0.03), _record(2028, acc_gain=0.05)]
    summary = summarize(records)
    assert math.isclose(summary["mean"]["accuracy"], float(_v2()["accuracy"]) + 0.03, rel_tol=1e-9)
    # population std of gains {0.01, 0.03, 0.05} = sqrt(2/3)/... -> 0.01632993...
    assert math.isclose(summary["std"]["accuracy"], 0.016329931618554516, rel_tol=1e-6)
