"""Regression tests for the V3.3 data-isolation and bounded-residual audit fixes.

These pin the ten mandatory corrections from the independent audit:
split-access enforcement, per-seed validation fingerprints, real (non-copied) A0
inference, a strictly bounded final residual, OOD metrics entering selection, the
pilot minimum-improvement threshold blocking promotion, and a complete pilot hash
guard.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import torch
import yaml

from datasets.synthetic_dataset import SyntheticModulationDataset
from evaluation.evaluate_qam_aware_v3_3 import evaluate_v3_3_a0_validation
from models.qam_aware_rfnet_v3_3 import build_qam_aware_v3_3, load_v2_into_v3_3
from training.qam_aware_v3_3_utils import load_qam_aware_v3_3_config
from training.select_qam_aware_v3_3_candidate import select_candidate
from training.v3_3_split_guard import (
    enter_selection_scope,
    exit_selection_scope,
    record_split,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V2_CHECKPOINT = PROJECT_ROOT / "init" / "v2_time_power_phase_best.pt"
SMOKE_CONFIG = "configs/qam_aware_v3_3_smoke.yaml"
CLASSES = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]


def _seed_metrics(macro_f1: float, accuracy: float = 0.7, *, worst_domain: float | None = None,
                  per_class: float = 0.7, fpga_gap: float = 0.0) -> dict:
    if worst_domain is None:
        worst_domain = macro_f1
    seed = {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "qam_mean_accuracy": 0.5,
        "per_class_accuracy": {name: per_class for name in CLASSES},
        "fpga_sim_accuracy_gap": fpga_gap,
        "fpga_sim_macro_f1_gap": 0.0,
        "ood": {"worst_domain_macro_f1": worst_domain, "domains": []},
    }
    return seed


def _record(name: str, seeds: dict, *, trained: bool = True) -> dict:
    return {
        "variant": name,
        "trained": trained,
        "seeds": seeds,
        "model": {"residual_expert": {"enabled": trained}},
        "training": {"residual_penalty_weight": 0.01},
    }


def test_selection_scope_rejects_forbidden_splits_immediately() -> None:
    enter_selection_scope()
    try:
        with pytest.raises(RuntimeError):
            record_split("test")
        with pytest.raises(RuntimeError):
            record_split("v3_3_final_blind_test")
        # Validation and OOD splits are allowed inside the scope.
        record_split("v3_3_validation")
        record_split("ood_cfo_strong")
    finally:
        exit_selection_scope()


def test_two_selection_seeds_generate_different_validation_fingerprints() -> None:
    config = load_qam_aware_v3_3_config(SMOKE_CONFIG)

    def fingerprints(seed: int) -> set[str]:
        dataset = SyntheticModulationDataset(
            64, config["signal"], None, seed, "v3_3_validation",
            snr_values=config["dataset"]["snr_values"],
        )
        return {hashlib.sha256(dataset[i][0].numpy().tobytes()).hexdigest() for i in range(64)}

    fp_2026 = fingerprints(2026)
    fp_2027 = fingerprints(2027)
    assert fp_2026 and fp_2027
    assert not (fp_2026 & fp_2027), "two selection seeds must yield distinct validation data"


def test_a0_infers_real_metrics_not_hardcoded() -> None:
    r_2026 = evaluate_v3_3_a0_validation(SMOKE_CONFIG, seed=2026)
    r_2027 = evaluate_v3_3_a0_validation(SMOKE_CONFIG, seed=2027)
    m_2026 = {key: float(r_2026["validation"][key]) for key in ("accuracy", "macro_f1", "qam_mean_accuracy")}
    m_2027 = {key: float(r_2027["validation"][key]) for key in ("accuracy", "macro_f1", "qam_mean_accuracy")}
    assert m_2026 != m_2027, "A0 metrics must come from real inference, not a copied constant"
    # Real inference must not reproduce the acceptance YAML's test-namespace constant.
    gate = yaml.safe_load((PROJECT_ROOT / "configs" / "qam_aware_v3_3_acceptance.yaml").read_text(encoding="utf-8"))
    assert abs(m_2026["accuracy"] - float(gate["v2"]["accuracy"])) > 1e-9


def test_final_residual_strictly_bounded_under_any_input() -> None:
    checkpoint = torch.load(V2_CHECKPOINT, map_location="cpu", weights_only=False)
    model = build_qam_aware_v3_3(
        8,
        simulate_hardware_inputs=False,
        time_base_channels=22,
        physical_base_channels=8,
        fusion_features=64,
        dropout=0.1,
        residual_expert={"enabled": True, "moment_order": 4, "hidden": 32, "gate_init": 0.0, "residual_bound": 1.0},
        family_aux={"enabled": False},
    )
    load_v2_into_v3_3(model, checkpoint)
    # Drive the expert to extreme values: without the clamp the residual would explode.
    with torch.no_grad():
        for parameter in model.core.expert.parameters():
            parameter.mul_(50.0)
        model.core.expert.gate.copy_(torch.tensor([100.0]))
    model.eval()
    bound = 1.0
    for seed in range(3):
        torch.manual_seed(seed)
        iq = torch.randn(8, 2, 1024) * 5.0
        _, aux = model.forward_with_aux(iq)
        residual = aux["residual"]
        assert residual.abs().max().item() <= bound + 1e-5
    # The gate (before clamp) is huge, proving the bound is enforced by the clamp.
    assert abs(float(model.core.expert.gate.item())) > bound


def test_ood_worst_domain_macro_f1_enters_selection() -> None:
    summary = {
        "variants": [
            _record("a0_frozen_v2", {"2026": _seed_metrics(0.60, worst_domain=0.60),
                                     "2027": _seed_metrics(0.60, worst_domain=0.60)}, trained=False),
            _record("robust", {"2026": _seed_metrics(0.70, worst_domain=0.65),
                               "2027": _seed_metrics(0.70, worst_domain=0.65)}),
            _record("fragile", {"2026": _seed_metrics(0.70, worst_domain=0.40),
                                "2027": _seed_metrics(0.70, worst_domain=0.40)}),
        ]
    }
    candidate = select_candidate(summary)
    assert candidate["selected_variant"] == "robust"


def test_below_threshold_blocks_promotion_and_formal_run() -> None:
    summary = {
        "variants": [
            _record("a0_frozen_v2", {"2026": _seed_metrics(0.70), "2027": _seed_metrics(0.70)}, trained=False),
            _record("a1", {"2026": _seed_metrics(0.705), "2027": _seed_metrics(0.705)}),
        ]
    }
    candidate = select_candidate(summary, minimum_improvement_threshold=0.01)
    assert candidate["selected_variant"] == "a1"
    assert candidate["promoted"] is False
    assert candidate["promotion_blocked_by"] == "below_improvement_threshold"


def test_pilot_hash_guard_covers_all_inputs() -> None:
    script = (PROJECT_ROOT / "autodl_v3_3" / "run_pilot.sh").read_text(encoding="utf-8")
    required = [
        "configs/qam_aware_v3_3_stage1.yaml",
        "configs/qam_aware_v3_3.yaml",
        "configs/qam_aware_v3_3_acceptance.yaml",
        "configs/baseline.yaml",
        "models/qam_aware_rfnet_v3_3.py",
        "training/qam_aware_v3_3_trainer.py",
        "training/train_qam_aware_v3_3.py",
        "training/select_qam_aware_v3_3_candidate.py",
        "training/narrow_search_v3_3.py",
        "training/v3_3_split_guard.py",
        "scripts/run_qam_aware_v3_3_stage1.py",
        "evaluation/evaluate_qam_aware_v3_3.py",
        "evaluation/evaluate_qam_aware_v3_3_ood.py",
        "init/v2_time_power_phase_best.pt",
    ]
    for item in required:
        assert item in script, f"pilot hash guard is missing dependency {item}"
