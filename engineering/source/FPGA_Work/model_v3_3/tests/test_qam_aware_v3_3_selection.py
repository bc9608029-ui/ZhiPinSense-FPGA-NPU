"""The V3.3 Stage-1 winner is chosen by a fixed two-seed lexicographic rule.

These tests pin the final training-selection closure:

* the new ``select_candidate(summary, *, minimum_improvement_threshold, pilot_gates)``
  contract (no ``v2`` parameter — the baseline is the same-seed A0 *inside* the
  ablation summary, never the acceptance YAML's V2 test-namespace numbers);
* every pilot hard gate (#1-#7) disqualifying a trained candidate;
* the same-seed / same-domain A0 baseline;
* the narrow search running by default only on the actual Stage-1 winner, and its
  winning config being frozen into ``selected_candidate`` (or discarded when the
  tuned result is worse than the untuned winner).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import scripts.run_qam_aware_v3_3_stage1 as stage1
from scripts.run_qam_aware_v3_3_stage1 import _should_run_narrow_search
from training.narrow_search_v3_3 import SEARCH_SPACE, _apply_point
from training.select_qam_aware_v3_3_candidate import SELECTION_RULE, select_candidate

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLASSES = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]


# --------------------------------------------------------------------------- #
# Synthetic summary builders
# --------------------------------------------------------------------------- #

def _pc(value: float = 0.70) -> dict[str, float]:
    return {name: float(value) for name in CLASSES}


def _domains(macro_f1: float = 0.65, per_class: float = 0.65,
             names: tuple[str, ...] = ("cfo_strong",)) -> list[dict]:
    return [
        {"domain": name, "macro_f1": float(macro_f1),
         "per_class_accuracy": {c: float(per_class) for c in CLASSES}}
        for name in names
    ]


def _seed(macro_f1: float, accuracy: float = 0.70, *, qam: float = 0.5,
          per_class: float = 0.70, fpga_gap: float = 0.0, fpga_mf_gap: float = 0.0,
          domains: list[dict] | None = None) -> dict:
    domains = _domains() if domains is None else domains
    return {
        "accuracy": float(accuracy),
        "macro_f1": float(macro_f1),
        "qam_mean_accuracy": float(qam),
        "per_class_accuracy": _pc(per_class),
        "fpga_sim_accuracy_gap": float(fpga_gap),
        "fpga_sim_macro_f1_gap": float(fpga_mf_gap),
        "ood": {
            "worst_domain_macro_f1": min(d["macro_f1"] for d in domains),
            "domains": domains,
        },
    }


def _record(name: str, seeds: dict, *, trained: bool = True, model=None, training=None) -> dict:
    return {
        "variant": name,
        "trained": trained,
        "seeds": seeds,
        "model": model if model is not None else {"residual_expert": {"enabled": trained}},
        "training": training if training is not None else {"residual_penalty_weight": 0.01},
    }


def _a0(macro_f1: float = 0.6975, accuracy: float = 0.705, *, per_class: float = 0.70,
        qam: float = 0.4648, domains: list[dict] | None = None) -> dict:
    seed = _seed(macro_f1, accuracy, qam=qam, per_class=per_class, domains=domains)
    return _record("a0_frozen_v2", {"2026": dict(seed), "2027": dict(seed)}, trained=False,
                   model={"residual_expert": {"enabled": False}},
                   training={"residual_penalty_weight": 0.0})


def _low_a0() -> dict:
    """A0 clearly below every trained candidate, so ranking tests are pure."""
    return _a0(macro_f1=0.50, accuracy=0.50, per_class=0.50, domains=_domains(0.50))


# --------------------------------------------------------------------------- #
# Fixed lexicographic ranking
# --------------------------------------------------------------------------- #

def test_selection_picks_highest_mean_macro_f1() -> None:
    summary = {"variants": [
        _low_a0(),
        _record("a1", {"2026": _seed(0.60, 0.9), "2027": _seed(0.62, 0.9)}),
        _record("a2", {"2026": _seed(0.71, 0.8), "2027": _seed(0.73, 0.8)}),
        _record("a3", {"2026": _seed(0.65, 0.85), "2027": _seed(0.67, 0.85)}),
    ]}
    assert select_candidate(summary)["selected_variant"] == "a2"


def test_selection_worst_seed_breaks_tie() -> None:
    summary = {"variants": [
        _low_a0(),
        _record("a1", {"2026": _seed(0.72, 0.8), "2027": _seed(0.60, 0.8)}),  # worst 0.60
        _record("a2", {"2026": _seed(0.68, 0.8), "2027": _seed(0.64, 0.8)}),  # worst 0.64
    ]}
    # Equal mean (0.66); a2 has the higher worst-seed macro-F1 and must win.
    assert select_candidate(summary)["selected_variant"] == "a2"


def test_a0_can_win_and_marks_no_promotion() -> None:
    summary = {"variants": [
        _record("a1", {"2026": _seed(0.60, 0.7), "2027": _seed(0.62, 0.7)}),
        _a0(macro_f1=0.70, accuracy=0.71),
    ]}
    candidate = select_candidate(summary)
    assert candidate["selected_variant"] == "a0_frozen_v2"
    assert candidate["promoted"] is False
    # a1 is uniformly worse than A0, so this is a plain A0 win, not a gate failure.
    assert candidate["promotion_blocked_by"] == "a0_won"


def test_a0_loses_when_a_trained_candidate_is_better() -> None:
    summary = {"variants": [
        _a0(macro_f1=0.6975, accuracy=0.705),
        _record("a1", {"2026": _seed(0.75, 0.78), "2027": _seed(0.76, 0.79)}),
    ]}
    candidate = select_candidate(summary)
    assert candidate["selected_variant"] == "a1"
    assert candidate["promoted"] is True


def test_selection_rejects_missing_seeds() -> None:
    summary = {"variants": [_a0(), _record("a1", {})]}
    with pytest.raises(RuntimeError):
        select_candidate(summary)


def test_two_seed_mean_and_worst_use_both_seeds() -> None:
    summary = {"variants": [
        _low_a0(),
        _record("a1", {"2026": _seed(0.8, 0.9), "2027": _seed(0.6, 0.7)}),
        _record("a2", {"2026": _seed(0.72, 0.9), "2027": _seed(0.72, 0.9)}),
    ]}
    # a1 mean = 0.70, a2 mean = 0.72 -> a2 wins even though a1's best seed (0.80) is
    # higher; the mean must not be cherry-picked.
    assert select_candidate(summary)["selected_variant"] == "a2"


def test_worst_class_regression_breaks_remaining_ties() -> None:
    # A0 per-class 0.70 sits between the two candidates so the regression metric
    # differs (good: 0.0, bad: +0.02) while every primary metric ties.
    a0 = _a0(macro_f1=0.68, accuracy=0.60, per_class=0.70, domains=_domains(0.60))
    good = _record("good", {"2026": _seed(0.70, 0.8, per_class=0.75),
                            "2027": _seed(0.70, 0.8, per_class=0.75)})
    bad = _record("bad", {"2026": _seed(0.70, 0.8, per_class=0.68),
                          "2027": _seed(0.70, 0.8, per_class=0.68)})
    assert select_candidate({"variants": [a0, bad, good]})["selected_variant"] == "good"


def test_fpga_sim_gap_breaks_remaining_ties() -> None:
    a0 = _a0(macro_f1=0.68, accuracy=0.60, per_class=0.70, domains=_domains(0.60))
    low_gap = _record("low_gap", {"2026": _seed(0.70, 0.8, per_class=0.75, fpga_gap=0.0),
                                  "2027": _seed(0.70, 0.8, per_class=0.75, fpga_gap=0.0)})
    high_gap = _record("high_gap", {"2026": _seed(0.70, 0.8, per_class=0.75, fpga_gap=0.03),
                                    "2027": _seed(0.70, 0.8, per_class=0.75, fpga_gap=0.03)})
    candidate = select_candidate({"variants": [a0, high_gap, low_gap]})
    assert candidate["selected_variant"] == "low_gap"
    assert candidate["selection_rule"] == SELECTION_RULE


# --------------------------------------------------------------------------- #
# A0 baseline contract (no `v2` argument; A0 must live in the summary)
# --------------------------------------------------------------------------- #

def test_selection_requires_a0_in_summary() -> None:
    with pytest.raises(RuntimeError):
        select_candidate({"variants": [_record("a1", {"2026": _seed(0.7), "2027": _seed(0.7)})]})


# --------------------------------------------------------------------------- #
# Pilot hard gates (#1-#7)
# --------------------------------------------------------------------------- #

def _default_a1() -> dict:
    return _record("a1", {
        "2026": _seed(0.75, 0.78, per_class=0.75, domains=_domains(0.70)),
        "2027": _seed(0.75, 0.78, per_class=0.75, domains=_domains(0.70)),
    })


def _default_a0() -> dict:
    return _a0(macro_f1=0.6975, accuracy=0.705, per_class=0.70, domains=_domains(0.70))


def _assert_gate_fails(a1: dict, gate: str, seed: str | None = None) -> dict:
    candidate = select_candidate({"variants": [_default_a0(), a1]})
    assert candidate["promoted"] is False
    failures = candidate["pilot_gate_report"]["a1"]["failures"]
    assert failures, "expected at least one pilot-gate failure"
    if seed is None:
        assert any(f["gate"] == gate for f in failures), failures
    else:
        assert any(f["gate"] == gate and f["seed"] == seed for f in failures), failures
    return candidate


def test_gate2_worst_seed_below_a0_blocks_promotion() -> None:
    a1 = _default_a1()
    a1["seeds"]["2027"]["macro_f1"] = 0.69  # < A0 2027 = 0.6975
    cand = _assert_gate_fails(a1, "worst_seed_macro_f1_below_a0", "2027")
    assert cand["promotion_blocked_by"] == "pilot_gate_failed"


def test_gate3_ood_domain_regression_blocks_promotion() -> None:
    a0 = _a0(per_class=0.70, domains=_domains(0.70, names=("cfo_strong", "snr_low")))
    a1 = _record("a1", {
        "2026": _seed(0.75, 0.78, per_class=0.75, domains=_domains(0.70, names=("cfo_strong", "snr_low"))),
        "2027": _seed(0.75, 0.78, per_class=0.75, domains=_domains(0.70, names=("cfo_strong", "snr_low"))),
    })
    a1["seeds"]["2027"]["ood"]["domains"][1]["macro_f1"] = 0.68  # snr_low drops 0.02 > 0.01
    candidate = select_candidate({"variants": [a0, a1]})
    assert candidate["promoted"] is False
    assert any(f["gate"] == "ood_domain_regression" and f["seed"] == "2027"
               for f in candidate["pilot_gate_report"]["a1"]["failures"])


def test_gate4_per_class_accuracy_drop_blocks_promotion() -> None:
    a1 = _default_a1()
    a1["seeds"]["2027"]["per_class_accuracy"]["BPSK"] = 0.66  # < A0 0.70 - 0.03
    _assert_gate_fails(a1, "per_class_accuracy_drop", "2027")


def test_gate5_fpga_sim_accuracy_gap_blocks_promotion() -> None:
    a1 = _default_a1()
    a1["seeds"]["2026"]["fpga_sim_accuracy_gap"] = 0.04  # > 0.03
    _assert_gate_fails(a1, "fpga_sim_accuracy_gap", "2026")


def test_gate6_fpga_sim_macro_f1_gap_blocks_promotion() -> None:
    a1 = _default_a1()
    a1["seeds"]["2026"]["fpga_sim_macro_f1_gap"] = 0.04  # > 0.03
    _assert_gate_fails(a1, "fpga_sim_macro_f1_gap", "2026")


def test_gate7_non_finite_metric_blocks_promotion() -> None:
    a1 = _default_a1()
    a1["seeds"]["2026"]["macro_f1"] = float("nan")
    candidate = select_candidate({"variants": [_default_a0(), a1]})
    assert candidate["promoted"] is False
    assert candidate["selected_variant"] == "a0_frozen_v2"
    assert any(f["gate"] == "non_finite_or_missing"
               for f in candidate["pilot_gate_report"]["a1"]["failures"])


def test_gate1_below_improvement_threshold_blocks_promotion() -> None:
    summary = {"variants": [
        _a0(macro_f1=0.70, accuracy=0.71, per_class=0.70, domains=_domains(0.70)),
        _record("a1", {"2026": _seed(0.705, per_class=0.70, domains=_domains(0.70)),
                       "2027": _seed(0.705, per_class=0.70, domains=_domains(0.70))}),
    ]}
    candidate = select_candidate(summary, minimum_improvement_threshold=0.01)
    assert candidate["selected_variant"] == "a1"
    assert candidate["promoted"] is False
    assert candidate["promotion_blocked_by"] == "below_improvement_threshold"


# --------------------------------------------------------------------------- #
# Fix 3: same-seed / same-domain A0 baseline
# --------------------------------------------------------------------------- #

def test_pilot_gate_uses_same_seed_a0_baseline() -> None:
    # A0 is strong on seed 2027 (0.75) and weak on seed 2026 (0.65).  The candidate
    # is 0.74 on seed 2027, which is ABOVE the seed-2026 A0 (0.65) but BELOW the
    # same-seed A0 (0.75) -> it must fail, proving per-seed (not pooled) baselines.
    a0 = _record("a0_frozen_v2", {
        "2026": _seed(0.65, 0.65, per_class=0.65, domains=_domains(0.60)),
        "2027": _seed(0.75, 0.75, per_class=0.75, domains=_domains(0.70)),
    }, trained=False, model={"residual_expert": {"enabled": False}},
       training={"residual_penalty_weight": 0.0})
    a1 = _record("a1", {
        "2026": _seed(0.66, 0.70, per_class=0.70, domains=_domains(0.60)),
        "2027": _seed(0.74, 0.75, per_class=0.75, domains=_domains(0.70)),
    })
    candidate = select_candidate({"variants": [a0, a1]})
    assert candidate["promoted"] is False
    assert any(f["gate"] == "worst_seed_macro_f1_below_a0" and f["seed"] == "2027"
               for f in candidate["pilot_gate_report"]["a1"]["failures"])


def test_ood_regression_compared_same_seed_same_domain() -> None:
    # A0's snr_low domain differs across seeds; dropping a single domain in a single
    # seed must be caught only against the same-seed, same-domain A0 value.
    a0 = _record("a0_frozen_v2", {
        "2026": _seed(0.65, 0.65, per_class=0.65,
                      domains=_domains(0.60, names=("cfo_strong", "snr_low"))),
        "2027": _seed(0.75, 0.75, per_class=0.75,
                      domains=_domains(0.70, names=("cfo_strong", "snr_low"))),
    }, trained=False, model={"residual_expert": {"enabled": False}},
       training={"residual_penalty_weight": 0.0})
    a1 = _record("a1", {
        "2026": _seed(0.66, 0.70, per_class=0.70,
                      domains=_domains(0.60, names=("cfo_strong", "snr_low"))),
        "2027": _seed(0.76, 0.75, per_class=0.75,
                      domains=[{"domain": "cfo_strong", "macro_f1": 0.70, "per_class_accuracy": _pc(0.75)},
                               {"domain": "snr_low", "macro_f1": 0.68, "per_class_accuracy": _pc(0.75)}]),
    })
    candidate = select_candidate({"variants": [a0, a1]})
    assert candidate["promoted"] is False
    assert any(f["gate"] == "ood_domain_regression" and f["seed"] == "2027"
               for f in candidate["pilot_gate_report"]["a1"]["failures"])


def test_stage1_ranking_uses_summary_a0_not_acceptance_v2() -> None:
    # The Stage-1 selection source never opens the acceptance config, so changing
    # its V2 test-namespace per-class can never change the validation ranking.
    src = (PROJECT_ROOT / "training" / "select_qam_aware_v3_3_candidate.py").read_text(encoding="utf-8")
    assert "qam_aware_v3_3_acceptance" not in src
    # Functional proof: summary A0 per-class is 0.90 (far above the acceptance V2
    # per-class ~0.7).  A candidate at 0.85 regresses vs the summary A0 (gate #4
    # fails) even though it would IMPROVE against the acceptance V2 number.
    a0 = _a0(macro_f1=0.85, accuracy=0.85, per_class=0.90, domains=_domains(0.85))
    a1 = _record("a1", {
        "2026": _seed(0.86, 0.86, per_class=0.85, domains=_domains(0.85)),
        "2027": _seed(0.86, 0.86, per_class=0.85, domains=_domains(0.85)),
    })
    candidate = select_candidate({"variants": [a0, a1]})
    assert any(f["gate"] == "per_class_accuracy_drop"
               for f in candidate["pilot_gate_report"]["a1"]["failures"])


# --------------------------------------------------------------------------- #
# Fix 1: narrow search — default run, actual-winner target, no fixed A3
# --------------------------------------------------------------------------- #

def _prelim(winner_trained: bool, improvement: float | None, threshold: float = 0.01) -> dict:
    return {"winner_trained": winner_trained, "improvement_over_a0": improvement,
            "minimum_improvement_threshold": threshold}


def test_narrow_search_runs_by_default_for_passing_winner() -> None:
    assert _should_run_narrow_search(_prelim(True, 0.02), {"enabled": True}) is True


def test_narrow_search_skipped_on_a0_win() -> None:
    assert _should_run_narrow_search(_prelim(False, None), {"enabled": True}) is False


def test_narrow_search_skipped_below_threshold() -> None:
    assert _should_run_narrow_search(_prelim(True, 0.005), {"enabled": True}) is False


def test_narrow_search_skipped_when_disabled() -> None:
    assert _should_run_narrow_search(_prelim(True, 0.02), {"enabled": False}) is False


def test_narrow_search_default_enabled_in_stage1_config() -> None:
    cfg = yaml.safe_load((PROJECT_ROOT / "configs" / "qam_aware_v3_3_stage1.yaml").read_text(encoding="utf-8"))
    assert cfg["narrow_search"]["enabled"] is True


def test_search_space_is_only_expert_knobs() -> None:
    assert set(SEARCH_SPACE) == {
        "learning_rate", "residual_bound", "residual_penalty_weight",
        "family_aux_loss_weight", "domain_consistency_weight",
    }


def test_apply_point_touches_knobs_not_mechanism() -> None:
    base_model = {"residual_expert": {"enabled": True, "moment_order": 4, "hidden": 32,
                                      "gate_init": 0.0, "residual_bound": 1.0},
                  "family_aux": {"enabled": True, "hidden": 16}}
    base_training = {"residual_penalty_weight": 0.01, "family_aux_loss_weight": 1.0,
                     "domain_consistency": {"enabled": True, "weight": 1.0, "mechanism": "consistency"}}
    point = {"learning_rate": 0.001, "residual_bound": 0.8, "residual_penalty_weight": 0.02,
             "family_aux_loss_weight": 0.5, "domain_consistency_weight": 0.3}
    model, training = _apply_point(base_model, base_training, point)
    assert model["residual_expert"]["enabled"] is True
    assert model["residual_expert"]["residual_bound"] == 0.8
    assert model["family_aux"]["enabled"] is True
    assert training["learning_rate"] == 0.001
    assert training["residual_penalty_weight"] == 0.02
    assert training["family_aux_loss_weight"] == 0.5
    assert training["domain_consistency"]["mechanism"] == "consistency"
    assert training["domain_consistency"]["weight"] == 0.3


def test_narrow_search_no_fixed_a3_mechanism() -> None:
    src = (PROJECT_ROOT / "training" / "narrow_search_v3_3.py").read_text(encoding="utf-8")
    assert "a3_domain_consistency" not in src
    cfg = yaml.safe_load((PROJECT_ROOT / "configs" / "qam_aware_v3_3_stage1.yaml").read_text(encoding="utf-8"))
    assert "base_variant" not in cfg.get("narrow_search", {})


def test_orchestrator_targets_actual_stage1_winner() -> None:
    src = (PROJECT_ROOT / "scripts" / "run_qam_aware_v3_3_stage1.py").read_text(encoding="utf-8")
    assert 'winner_variant=prelim["selected_variant"]' in src


# --------------------------------------------------------------------------- #
# Fix 1: the search result is frozen into selected_candidate (never reference-only)
# --------------------------------------------------------------------------- #

def _run_orchestrator(monkeypatch, tmp_path, summary, tuned) -> dict:
    """Run ``run_stage1_and_select`` with the training/search layers stubbed out."""
    captured: dict = {}
    cfg = tmp_path / "stage1.yaml"
    cfg.write_text(yaml.safe_dump({
        "pilot": {"minimum_improvement_threshold": 0.01},
        "narrow_search": {"enabled": True},
    }), encoding="utf-8")
    summ = tmp_path / "ablation_summary.json"
    summ.write_text(json.dumps(summary), encoding="utf-8")

    monkeypatch.setattr(stage1, "ABLATION_SUMMARY", str(summ))
    monkeypatch.setattr(stage1, "run_stage1", lambda path: summary)
    monkeypatch.setattr(stage1, "run_narrow_search", lambda *a, **k: tuned)
    monkeypatch.setattr(stage1, "write_candidate",
                        lambda c, out: (captured.__setitem__("candidate", c), c)[1])
    monkeypatch.setattr(stage1, "resolve_project_path", lambda p: Path(p))

    stage1.run_stage1_and_select(str(cfg), str(tmp_path / "selected.yaml"))
    return captured["candidate"]


def _tuned(macro_f1: float, *, training=None) -> dict:
    record = _record("a1_tuned", {
        "2026": _seed(macro_f1, 0.78, per_class=0.75, domains=_domains(0.70)),
        "2027": _seed(macro_f1, 0.78, per_class=0.75, domains=_domains(0.70)),
    }, training=training)
    record["tuned"] = True
    record["base_variant"] = "a1"
    return record


def test_tuned_winner_is_frozen_into_selected_candidate(monkeypatch, tmp_path) -> None:
    summary = {"variants": [
        _a0(macro_f1=0.6975, accuracy=0.705, per_class=0.70, domains=_domains(0.70)),
        _record("a1", {"2026": _seed(0.75, 0.78, per_class=0.75, domains=_domains(0.70)),
                       "2027": _seed(0.76, 0.78, per_class=0.75, domains=_domains(0.70))}),
    ]}
    tuned = _tuned(0.78, training={"residual_penalty_weight": 0.99})
    candidate = _run_orchestrator(monkeypatch, tmp_path, summary, tuned)
    assert candidate["narrow_search_ran"] is True
    assert candidate["narrow_search_base_variant"] == "a1"
    assert candidate["selected_variant"] == "a1_tuned"
    assert candidate["promoted"] is True
    # The tuned config — not the untuned a1 config — is what gets frozen.
    assert candidate["training"]["residual_penalty_weight"] == 0.99


def test_tuned_worse_keeps_untuned_winner(monkeypatch, tmp_path) -> None:
    summary = {"variants": [
        _a0(macro_f1=0.6975, accuracy=0.705, per_class=0.70, domains=_domains(0.70)),
        _record("a1", {"2026": _seed(0.75, 0.78, per_class=0.75, domains=_domains(0.70)),
                       "2027": _seed(0.76, 0.78, per_class=0.75, domains=_domains(0.70))},
                training={"residual_penalty_weight": 0.01}),
    ]}
    tuned = _tuned(0.73, training={"residual_penalty_weight": 0.99})  # worse than a1
    candidate = _run_orchestrator(monkeypatch, tmp_path, summary, tuned)
    assert candidate["narrow_search_ran"] is True
    assert candidate["selected_variant"] == "a1"  # untuned winner kept
    assert candidate["training"]["residual_penalty_weight"] == 0.01


def test_a0_win_skips_narrow_search(monkeypatch, tmp_path) -> None:
    summary = {"variants": [
        _record("a1", {"2026": _seed(0.60, 0.7), "2027": _seed(0.62, 0.7)}),
        _a0(macro_f1=0.70, accuracy=0.71),
    ]}

    def boom(*a, **k):
        raise AssertionError("narrow search must not run when A0 wins")

    monkeypatch.setattr(stage1, "run_narrow_search", boom)
    candidate = _run_orchestrator(monkeypatch, tmp_path, summary, tuned=None)
    assert candidate["narrow_search_ran"] is False
    assert candidate["selected_variant"] == "a0_frozen_v2"
    assert candidate["promoted"] is False
