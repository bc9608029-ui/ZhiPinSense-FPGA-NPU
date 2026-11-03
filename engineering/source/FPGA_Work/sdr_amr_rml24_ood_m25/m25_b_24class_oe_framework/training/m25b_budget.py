"""Phase-1 hard ID-protection budget gate for the M25-B OE verify run.

The seed-2026 OE run must not degrade the frozen baseline's closed-set behaviour,
so a battery of hard checks gates promotion.  Any single failure produces
``OE_DECISION result=REJECT`` with a reason list; only a clean pass produces
``OE_DECISION result=PROMOTE``.
"""
from __future__ import annotations

from typing import Any, Callable

from training.m25b_oe_controls import DECISION_PROMOTE, DECISION_REJECT

# Frozen tolerances (phase-1 hard gate; never loosen to make OE pass).
ACC_OVERALL_TOL = 0.01      # overall accuracy may drop at most 1 pp
MACRO_F1_TOL = 0.01         # macro-F1 may drop at most 1 pp
RATED_0_20_TOL = 0.005      # rated_0_20_accuracy may drop at most 0.5 pp
MIN_CLASS_TOL = 0.02        # per-class accuracy may drop at most 2 pp
LOW_SNR_TOL = 0.02          # low-SNR ID accept may drop at most 2 pp
ROBUSTNESS_TOL = 0.02       # CFO/multipath/phase-noise/IQ-imb/clipping accept drop

ROBUSTNESS_FIELDS = ("cfo", "multipath", "phase_noise", "iq_imbalance", "clipping")

# Near OOD must not degrade (by more than a tiny tolerance); far OOD must improve.
NEAR_OOD_TOL = 0.0          # near may not degrade at all
FAR_OOD_AUROC_GAIN = 0.02   # far AUROC must improve by at least this


def _drop(base: float, now: float) -> float:
    return float(base) - float(now)


def check_id_accuracy(baseline: dict[str, Any], oe: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    b = float(baseline.get("overall_accuracy", 0.0))
    o = float(oe.get("overall_accuracy", 0.0))
    if _drop(b, o) > ACC_OVERALL_TOL:
        reasons.append(f"overall_accuracy_drop={_drop(b, o):.4f}>{ACC_OVERALL_TOL}")
    bf = float(baseline.get("macro_f1", 0.0))
    of = float(oe.get("macro_f1", 0.0))
    if _drop(bf, of) > MACRO_F1_TOL:
        reasons.append(f"macro_f1_drop={_drop(bf, of):.4f}>{MACRO_F1_TOL}")
    br = float(baseline.get("rated_0_20_accuracy", 0.0))
    orr = float(oe.get("rated_0_20_accuracy", 0.0))
    if _drop(br, orr) > RATED_0_20_TOL:
        reasons.append(f"rated_0_20_drop={_drop(br, orr):.4f}>{RATED_0_20_TOL}")
    return reasons


def check_min_class(baseline: dict[str, Any], oe: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    b = baseline.get("per_class_accuracy") or {}
    o = oe.get("per_class_accuracy") or {}
    for label, base in b.items():
        now = o.get(label, 0.0)
        if _drop(float(base), float(now)) > MIN_CLASS_TOL:
            reasons.append(f"min_class_drop[{label}]={_drop(float(base), float(now)):.4f}>{MIN_CLASS_TOL}")
    return reasons


def check_low_snr(baseline: dict[str, Any], oe: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    b = float(baseline.get("low_snr_id_accept", 1.0))
    o = float(oe.get("low_snr_id_accept", 1.0))
    if _drop(b, o) > LOW_SNR_TOL:
        reasons.append(f"low_snr_id_accept_drop={_drop(b, o):.4f}>{LOW_SNR_TOL}")
    return reasons


def check_robustness(baseline: dict[str, Any], oe: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    b = baseline.get("robustness_id_accept") or {}
    o = oe.get("robustness_id_accept") or {}
    for field in ROBUSTNESS_FIELDS:
        base = float(b.get(field, 1.0))
        now = float(o.get(field, 1.0))
        if _drop(base, now) > ROBUSTNESS_TOL:
            reasons.append(f"robustness_id_accept_drop[{field}]={_drop(base, now):.4f}>{ROBUSTNESS_TOL}")
    return reasons


def check_ood(baseline: dict[str, Any], oe: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    b_near = float(baseline.get("near_ood_auroc", 0.0))
    o_near = float(oe.get("near_ood_auroc", 0.0))
    near_drop = b_near - o_near  # positive = near degraded
    if near_drop > NEAR_OOD_TOL:
        reasons.append(f"near_ood_degrade={near_drop:.4f}>{NEAR_OOD_TOL}")
    b_far = float(baseline.get("far_ood_auroc", 0.0))
    o_far = float(oe.get("far_ood_auroc", 0.0))
    far_gain = o_far - b_far  # positive = far improved
    if far_gain < FAR_OOD_AUROC_GAIN:
        reasons.append(f"far_ood_gain={far_gain:.4f}<{FAR_OOD_AUROC_GAIN}")
    return reasons


_CHECKS: tuple[tuple[str, Callable[[dict[str, Any], dict[str, Any]], list[str]]], ...] = (
    ("id_accuracy", check_id_accuracy),
    ("min_class", check_min_class),
    ("low_snr", check_low_snr),
    ("robustness", check_robustness),
    ("ood", check_ood),
)


def run_budget_gate(baseline: dict[str, Any], oe: dict[str, Any]) -> dict[str, Any]:
    """Run the phase-1 hard gate; fail-closed toward REJECT."""
    reasons: list[str] = []
    for name, fn in _CHECKS:
        reasons.extend(fn(baseline, oe))
    decision = "REJECT" if reasons else "PROMOTE"
    return {
        "decision": decision,
        "reasons": reasons,
        "status": DECISION_REJECT if reasons else DECISION_PROMOTE,
    }


__all__ = [
    "ACC_OVERALL_TOL", "MACRO_F1_TOL", "RATED_0_20_TOL", "MIN_CLASS_TOL",
    "LOW_SNR_TOL", "ROBUSTNESS_TOL", "ROBUSTNESS_FIELDS", "NEAR_OOD_TOL",
    "FAR_OOD_AUROC_GAIN", "check_id_accuracy", "check_min_class",
    "check_low_snr", "check_robustness", "check_ood", "run_budget_gate",
]
