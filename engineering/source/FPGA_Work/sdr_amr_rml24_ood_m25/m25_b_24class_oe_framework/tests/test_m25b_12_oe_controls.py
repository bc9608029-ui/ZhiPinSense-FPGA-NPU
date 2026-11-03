"""OE controls / promotion gate tests."""
from training import m25b_oe_controls as c


def _id(macro_f1, rated):
    return {"macro_f1": macro_f1, "rated_0_20_accuracy": rated}


def _ood(auroc, fpr95, oscr):
    return {"auroc": auroc, "fpr95": fpr95, "oscr": oscr}


def test_promote_when_ood_improves_and_id_stable():
    d = c.decide_oe_promotion(_id(0.90, 0.85), _id(0.90, 0.85),
                              _ood(0.70, 0.40, 0.60), _ood(0.75, 0.32, 0.64))
    assert d["decision"] == "PROMOTE"
    assert d["improved"]


def test_reject_on_id_degradation():
    d = c.decide_oe_promotion(_id(0.90, 0.85), _id(0.87, 0.85),  # macro drops 3pp
                              _ood(0.70, 0.40, 0.60), _ood(0.75, 0.32, 0.64))
    assert d["decision"] == "REJECT"
    assert any("id_macro_f1_drop" in r for r in d["reasons"])


def test_reject_when_no_ood_gain():
    d = c.decide_oe_promotion(_id(0.90, 0.85), _id(0.90, 0.85),
                              _ood(0.70, 0.40, 0.60), _ood(0.70, 0.40, 0.60))
    assert d["decision"] == "REJECT"
    assert "no_ood_gain" in d["reasons"]


def test_constants():
    assert c.OE_FIRST_SEED == 2026
    assert c.OE_EXTRA_SEEDS == (2027, 2028)
    assert set(c.CONTROLS) == {"baseline", "oe_energy", "oe_msp"}


def test_build_oe_report():
    report = c.build_oe_report(_id(0.9, 0.85), _id(0.9, 0.85),
                               _ood(0.7, 0.4, 0.6), _ood(0.75, 0.32, 0.64),
                               {"decision": "PROMOTE", "reasons": []})
    assert report["oe_seed"] == 2026
    assert report["decision"] == "PROMOTE"
