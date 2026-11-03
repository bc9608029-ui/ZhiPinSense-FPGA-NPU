"""V1.1 budget/dedup — OE+Energy 1+2 seed promotion gate (pure logic)."""

from __future__ import annotations

from training.oe_decision import (
    build_oe_report,
    decide_oe_promotion,
    energy_far_metrics,
    id_metrics_from_result,
)


def _id(macro: float = 0.85, rated: float = 0.80) -> dict:
    return {"macro_f1": macro, "rated_0_20_accuracy": rated}


def _ood(auroc: float = 0.70, fpr95: float = 0.40, oscr: float = 0.55) -> dict:
    return {"auroc": auroc, "fpr95": fpr95, "oscr": oscr}


def test_id_metrics_from_result() -> None:
    result = {"baseline": {"metrics": {"macro_f1": 0.85, "rated_0_20_accuracy": 0.80}}}
    assert id_metrics_from_result(result) == {"macro_f1": 0.85, "rated_0_20_accuracy": 0.80}


def test_energy_far_metrics_extracts_nested() -> None:
    report = {"families": {"energy": {"families": {"far": {
        "ranking": {"auroc": 0.72, "fpr95": 0.38},
        "oscr": {"auc_ccr_fpr": 0.60},
    }}}}}
    assert energy_far_metrics(report) == {"auroc": 0.72, "fpr95": 0.38, "oscr": 0.60}


def test_promote_on_auroc_gain_without_id_degradation() -> None:
    decision = decide_oe_promotion(_id(), _id(macro=0.845, rated=0.795),
                                   _ood(auroc=0.70), _ood(auroc=0.73))
    assert decision["decision"] == "PROMOTE"
    assert decision["improved"] == ["auroc"]


def test_promote_on_fpr95_gain() -> None:
    # FPR95 drops by 0.06 (> 0.05 gain).
    decision = decide_oe_promotion(_id(), _id(), _ood(fpr95=0.40), _ood(fpr95=0.34))
    assert decision["decision"] == "PROMOTE"
    assert "fpr95" in decision["improved"]


def test_promote_on_oscr_gain() -> None:
    decision = decide_oe_promotion(_id(), _id(), _ood(oscr=0.55), _ood(oscr=0.58))
    assert decision["decision"] == "PROMOTE"
    assert "oscr" in decision["improved"]


def test_reject_on_id_macro_degradation() -> None:
    # ID macro-F1 drops by 0.02 (> 0.01) even though OOD improves.
    decision = decide_oe_promotion(_id(macro=0.85), _id(macro=0.82),
                                   _ood(auroc=0.70), _ood(auroc=0.75))
    assert decision["decision"] == "REJECT"
    assert any("macro_f1" in r for r in decision["reasons"])


def test_reject_on_id_rated_degradation() -> None:
    decision = decide_oe_promotion(_id(rated=0.80), _id(rated=0.78),
                                   _ood(auroc=0.70), _ood(auroc=0.75))
    assert decision["decision"] == "REJECT"
    assert any("rated_acc" in r for r in decision["reasons"])


def test_reject_without_ood_gain() -> None:
    decision = decide_oe_promotion(_id(), _id(), _ood(auroc=0.70), _ood(auroc=0.71))
    assert decision["decision"] == "REJECT"
    assert "no_ood_gain" in decision["reasons"]


def test_build_oe_report_carries_decision_fields() -> None:
    decision = decide_oe_promotion(_id(), _id(), _ood(), _ood(auroc=0.73))
    report = build_oe_report(_id(), _id(), _ood(), _ood(auroc=0.73), decision)
    assert report["oe_seed"] == 2026
    assert report["decision"] == "PROMOTE"
    assert report["tolerances"]["auroc_gain"] == 0.02
