"""V1.1 budget/dedup — canonical candidate signature.

Offline these tests exercise the pure signature logic (no GPU, no training): two
configs that differ only in training knobs must produce different identities,
while key order, the per-run seed, and volatile path/timestamp/run_id fields must
not.  The data provenance SHAs are required and fail closed when absent.
"""

from __future__ import annotations

import pytest

from contracts.rml24_contract import LABEL_ORDER_24
from v2.candidate_signature import (
    KEY_DATASET_SHA,
    KEY_LABEL_SHA,
    KEY_SPLIT_SHA,
    canonical_candidate_signature,
    config_sha256,
    label_contract_sha256,
)

_DS = "a" * 64
_SPLIT = "b" * 64


def _base_config() -> dict:
    return {
        "model": {
            "denoiser_channels": 24, "denoiser_blocks": 3,
            "feature_channels": [32, 48, 64, 96], "classifier_hidden": 128,
            "dropout": 0.15,
        },
        "rml24": {"model_name": "RML2018_24_BENCHMARK", "apply_channel_augmentation": False},
        "v2": {
            "loss": "focal", "focal_gamma": 2.0, "optimizer": "adamw",
            "class_sampling": "balanced", "sgd_momentum": 0.9,
        },
        "training": {
            "learning_rate": 1e-3, "weight_decay": 1e-4, "batch_size": 256,
            "scheduler_factor": 0.5, "scheduler_patience": 5, "minimum_lr": 1e-6,
            "amp": True, "amp_dtype": "bfloat16", "gradient_clip_norm": 2.0,
            "reconstruction_weight": 0.0, "snr_weighting": {"rated_snr_weight": 1.25},
            "minimum_epochs_before_stopping": 30, "early_stopping_patience": 12,
            "min_delta": 1e-4,
        },
        KEY_DATASET_SHA: _DS,
        KEY_SPLIT_SHA: _SPLIT,
        KEY_LABEL_SHA: label_contract_sha256(),
    }


def test_signature_is_deterministic_and_key_order_insensitive() -> None:
    a = _base_config()
    b = dict(reversed(list(a.items())))  # same content, different key order
    b["v2"] = dict(reversed(list(a["v2"].items())))
    b["training"] = dict(reversed(list(a["training"].items())))
    assert canonical_candidate_signature(a) == canonical_candidate_signature(b)
    assert len(canonical_candidate_signature(a)) == 64


def test_param_change_yields_different_signature() -> None:
    base = _base_config()
    changed = _base_config()
    changed["training"] = dict(changed["training"], learning_rate=3e-4)
    assert canonical_candidate_signature(changed) != canonical_candidate_signature(base)


def test_loss_change_yields_different_signature() -> None:
    base = _base_config()
    changed = _base_config()
    changed["v2"] = dict(changed["v2"], loss="cross_entropy")
    assert canonical_candidate_signature(changed) != canonical_candidate_signature(base)


def test_excluded_fields_do_not_change_signature() -> None:
    base = _base_config()
    noisy = _base_config()
    noisy.update({
        "seed": 999, "trial": "t000", "output_root": "runs/rml24_base/formal/t000/seed2026",
        "run_id": "run-abc-123", "_config_path": "/tmp/x.yaml",
        "checkpoint_path": "runs/checkpoints/best.pt",
        "log_path": "runs/logs/log.txt", "timestamp": "2026-10-08T00:00:00Z",
    })
    assert canonical_candidate_signature(noisy) == canonical_candidate_signature(base)


def test_epoch_budget_and_early_stopping_do_not_change_signature() -> None:
    # run_rml24_trial caps minimum_epochs_before_stopping to the (pilot) epoch budget;
    # the signature must stay stable across pilot (20 epochs) and formal (80 epochs).
    pilot = _base_config()
    pilot["training"] = dict(pilot["training"], epochs=20, minimum_epochs_before_stopping=20)
    formal = _base_config()
    formal["training"] = dict(formal["training"], epochs=80, minimum_epochs_before_stopping=30)
    assert canonical_candidate_signature(pilot) == canonical_candidate_signature(formal)


def test_missing_dataset_sha_fails_closed() -> None:
    cfg = _base_config()
    cfg.pop(KEY_DATASET_SHA)
    with pytest.raises(ValueError):
        canonical_candidate_signature(cfg)


def test_missing_split_sha_fails_closed() -> None:
    cfg = _base_config()
    cfg.pop(KEY_SPLIT_SHA)
    with pytest.raises(ValueError):
        canonical_candidate_signature(cfg)


def test_explicit_shas_override_config_keys() -> None:
    cfg = _base_config()
    # Config carries no SHAs but explicit kwargs supply them.
    cfg.pop(KEY_DATASET_SHA)
    cfg.pop(KEY_SPLIT_SHA)
    cfg.pop(KEY_LABEL_SHA)
    sig = canonical_candidate_signature(cfg, dataset_sha256=_DS, split_sha256=_SPLIT,
                                        label_contract_sha256=label_contract_sha256())
    assert sig == canonical_candidate_signature(_base_config())


def test_config_sha256_excludes_data_provenance() -> None:
    a = _base_config()
    b = _base_config()
    b[KEY_DATASET_SHA] = "c" * 64
    b[KEY_SPLIT_SHA] = "d" * 64
    # config_sha256 covers only training knobs, so changing provenance must not move it.
    assert config_sha256(a) == config_sha256(b)
    # The full candidate signature must move.
    assert canonical_candidate_signature(a) != canonical_candidate_signature(b)


def test_label_contract_sha_matches_frozen_order() -> None:
    assert label_contract_sha256() == label_contract_sha256()
    assert len(label_contract_sha256()) == 64
    assert len(LABEL_ORDER_24) == 24
    assert tuple(LABEL_ORDER_24) == LABEL_ORDER_24  # sanity: frozen tuple of 24
