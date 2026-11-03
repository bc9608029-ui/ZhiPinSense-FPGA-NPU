"""Phase-1 ID-protection budget gate tests."""
from training import m25b_budget as b


def _clean_pair():
    baseline = {
        "overall_accuracy": 0.90, "macro_f1": 0.88, "rated_0_20_accuracy": 0.85,
        "per_class_accuracy": {f"c{i}": 0.85 for i in range(24)},
        "low_snr_id_accept": 0.80,
        "robustness_id_accept": {k: 0.85 for k in b.ROBUSTNESS_FIELDS},
        "near_ood_auroc": 0.80, "far_ood_auroc": 0.75,
    }
    oe = {
        "overall_accuracy": 0.90, "macro_f1": 0.88, "rated_0_20_accuracy": 0.85,
        "per_class_accuracy": {f"c{i}": 0.85 for i in range(24)},
        "low_snr_id_accept": 0.80,
        "robustness_id_accept": {k: 0.85 for k in b.ROBUSTNESS_FIELDS},
        "near_ood_auroc": 0.81, "far_ood_auroc": 0.78,  # far improves +0.03
    }
    return baseline, oe


def test_clean_promotes():
    baseline, oe = _clean_pair()
    result = b.run_budget_gate(baseline, oe)
    assert result["decision"] == "PROMOTE"
    assert result["reasons"] == []


def test_overall_accuracy_drop_rejects():
    baseline, oe = _clean_pair()
    oe["overall_accuracy"] = 0.88  # -2pp
    result = b.run_budget_gate(baseline, oe)
    assert result["decision"] == "REJECT"
    assert any("overall_accuracy_drop" in r for r in result["reasons"])


def test_far_ood_no_gain_rejects():
    baseline, oe = _clean_pair()
    oe["far_ood_auroc"] = 0.75  # no gain
    result = b.run_budget_gate(baseline, oe)
    assert result["decision"] == "REJECT"
    assert any("far_ood_gain" in r for r in result["reasons"])


def test_min_class_collapse_rejects():
    baseline, oe = _clean_pair()
    oe["per_class_accuracy"]["c0"] = 0.70  # -15pp
    result = b.run_budget_gate(baseline, oe)
    assert result["decision"] == "REJECT"


def test_robustness_drop_rejects():
    baseline, oe = _clean_pair()
    oe["robustness_id_accept"]["cfo"] = 0.70  # -15pp
    result = b.run_budget_gate(baseline, oe)
    assert result["decision"] == "REJECT"
