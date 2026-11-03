"""The ablation winner is chosen by a fixed, validation-only rule."""

from __future__ import annotations

import pytest

from training.select_qam_aware_v3_2_candidate import SELECTION_RULE, select_candidate


def _variant(name: str, macro_f1: float, accuracy: float, *, qam_weight: float = 1.0, distill: bool = True) -> dict:
    return {
        "variant": name,
        "trained": True,
        "distill": distill,
        "qam_weight": qam_weight,
        "val_macro_f1": macro_f1,
        "val_accuracy": accuracy,
        "best_epoch": 1,
        "note": "",
        "training": {
            "distillation": {"enabled": distill, "temperature": 4.0, "alpha": 0.7},
            "class_weights": {"BPSK": 1.0, "16QAM": qam_weight, "64QAM": qam_weight},
        },
    }


def test_selection_picks_max_macro_f1() -> None:
    summary = {"variants": [_variant("a1", 0.5, 0.9), _variant("a2", 0.7, 0.8), _variant("a3", 0.6, 0.85)]}
    assert select_candidate(summary)["selected_variant"] == "a2"


def test_selection_tiebreak_uses_accuracy() -> None:
    summary = {"variants": [_variant("a1", 0.6, 0.80), _variant("a2", 0.6, 0.85)]}
    assert select_candidate(summary)["selected_variant"] == "a2"


def test_selection_ignores_non_validation_fields() -> None:
    # a1 would look better if a leaked v2_compatible score were consulted; a2 has
    # the higher validation macro-F1 and must win regardless.
    a1 = _variant("a1", 0.5, 0.7)
    a1["v2_compatible_accuracy"] = 0.99
    a2 = _variant("a2", 0.6, 0.7)
    a2["v2_compatible_accuracy"] = 0.01
    assert select_candidate({"variants": [a1, a2]})["selected_variant"] == "a2"


def test_selection_freezes_full_training_override() -> None:
    candidate = select_candidate({"variants": [_variant("a3", 0.9, 0.9, qam_weight=1.10)]})
    assert candidate["selected_variant"] == "a3"
    assert candidate["training"]["distillation"]["enabled"] is True
    assert candidate["training"]["class_weights"]["16QAM"] == 1.10
    assert candidate["selection_rule"] == SELECTION_RULE
    assert "final_blind_test" in candidate["selection_scope"]


def test_selection_rejects_nonfinite_metrics() -> None:
    with pytest.raises(RuntimeError):
        select_candidate({"variants": [_variant("a1", float("nan"), 0.5)]})


def test_selection_rejects_missing_training_override() -> None:
    bad = _variant("a1", 0.5, 0.5)
    del bad["training"]
    with pytest.raises(RuntimeError):
        select_candidate({"variants": [bad]})


def test_selection_skips_untrained_a0_reference() -> None:
    summary = {
        "variants": [
            {
                "variant": "a0_frozen_v2_reference",
                "trained": False,
                "val_macro_f1": None,
                "val_accuracy": None,
                "best_epoch": None,
            },
            _variant("a1", 0.4, 0.6),
        ]
    }
    assert select_candidate(summary)["selected_variant"] == "a1"
