"""V1.1 budget/dedup — pilot dedup and second-candidate promotion gate."""

from __future__ import annotations

import pytest

from training.rml24_select import _dedupe, _second_candidate_qualifies, apply_candidate
from v2.candidate_signature import (
    KEY_DATASET_SHA, KEY_LABEL_SHA, KEY_SPLIT_SHA,
    canonical_candidate_signature, label_contract_sha256,
)

_DS = "a" * 64
_SPLIT = "b" * 64


def _base() -> dict:
    return {
        "model": {"denoiser_channels": 24},
        "rml24": {"model_name": "RML2018_24_BENCHMARK", "apply_channel_augmentation": False},
        "v2": {"loss": "focal", "focal_gamma": 2.0, "optimizer": "adamw",
               "class_sampling": "balanced", "sgd_momentum": 0.9},
        "training": {"learning_rate": 1e-3, "weight_decay": 1e-4, "batch_size": 256,
                     "scheduler_factor": 0.5, "scheduler_patience": 5, "minimum_lr": 1e-6,
                     "amp": True, "amp_dtype": "bfloat16", "gradient_clip_norm": 2.0,
                     "reconstruction_weight": 0.0, "snr_weighting": {}},
        KEY_DATASET_SHA: _DS, KEY_SPLIT_SHA: _SPLIT, KEY_LABEL_SHA: label_contract_sha256(),
    }


def _result(trial: str, v2: dict, training: dict, rated: float, *,
            min_cls: float = 0.5, snr0: float = 0.7, per_class: list[float] | None = None) -> dict:
    per_class = per_class if per_class is not None else [0.9] * 24
    return {
        "trial": trial, "v2": dict(v2), "training": dict(training),
        "baseline": {"metrics": {
            "rated_0_20_accuracy": rated, "min_per_class_accuracy": min_cls,
            "snr_0_accuracy": snr0, "per_class_accuracy": per_class}},
    }


def test_dedupe_collapses_identical_configs_and_keeps_best() -> None:
    base = _base()
    v2 = {"loss": "focal", "focal_gamma": 2.0, "optimizer": "adamw", "class_sampling": "balanced"}
    training = {"learning_rate": 1e-3, "weight_decay": 1e-4}
    results = [
        _result("t000", v2, training, 0.80),
        _result("t001", v2, training, 0.90),  # identical config, better score
    ]
    unique, duplicates = _dedupe(results, base)
    assert len(unique) == 1
    assert unique[0]["trial"] == "t001"
    assert len(duplicates) == 1
    dup = duplicates[0]
    assert dup["kept_trial"] == "t001"
    assert dup["duplicate_trials"] == ["t000"]


def test_dedupe_keeps_distinct_configs_separate() -> None:
    base = _base()
    v2 = {"loss": "focal", "focal_gamma": 2.0, "optimizer": "adamw", "class_sampling": "balanced"}
    results = [
        _result("t000", v2, {"learning_rate": 1e-3, "weight_decay": 1e-4}, 0.80),
        _result("t001", v2, {"learning_rate": 3e-4, "weight_decay": 1e-4}, 0.85),
    ]
    unique, duplicates = _dedupe(results, base)
    assert len(unique) == 2
    assert duplicates == []


def test_second_candidate_promotes_on_score_within_tol_and_better_dim() -> None:
    # Same score delta 0.005, second beats first on worst-class recall.
    first = _result("t000", {}, {}, 0.90, min_cls=0.50, per_class=[0.9] * 24)
    second = _result("t001", {}, {}, 0.905, min_cls=0.60, per_class=[0.9] * 24)
    ok, reason = _second_candidate_qualifies(first, second)
    assert ok
    assert "worst_class_recall" in reason


def test_second_candidate_rejected_on_large_score_delta() -> None:
    first = _result("t000", {}, {}, 0.90, min_cls=0.50)
    second = _result("t001", {}, {}, 0.80, min_cls=0.80)
    ok, reason = _second_candidate_qualifies(first, second)
    assert not ok
    assert "score_delta" in reason


def test_second_candidate_rejected_without_key_dim_improvement() -> None:
    # score delta within tol, but no key dimension is better.
    first = _result("t000", {}, {}, 0.90, min_cls=0.50, snr0=0.70)
    second = _result("t001", {}, {}, 0.905, min_cls=0.50, snr0=0.70)
    ok, reason = _second_candidate_qualifies(first, second)
    assert not ok
    assert "not better" in reason
