"""OE controls and promotion gate for the M25-B 24-class framework.

Mirrors the V1.1 ``oe_decision`` design (self-contained, no cross-project import):

  - Frozen first seed 2026 is the *verify* run; 2027/2028 are the extra seeds.
  - Promote only when ID degradation is within tolerance AND at least one Energy
    OOD metric improves by the frozen margin; otherwise REJECT (fail-closed).
  - Three controls: frozen baseline postprocessing (``baseline``), OE+Energy
    (``oe_energy``), and optional OE+MSP (``oe_msp``).
"""
from __future__ import annotations

from typing import Any

OE_FIRST_SEED = 2026
OE_EXTRA_SEEDS = (2027, 2028)

CONTROLS = ("baseline", "oe_energy", "oe_msp")

ID_DEGRADATION_TOL = 0.01
OOD_AUROC_GAIN = 0.02
OOD_FPR95_GAIN = 0.05
OOD_OSCR_GAIN = 0.02

DECISION_PROMOTE = "OE_DECISION result=PROMOTE"
DECISION_REJECT = "OE_DECISION result=REJECT"


def id_metrics_from_result(result: dict[str, Any]) -> dict[str, float]:
    """Extract the closed-set ID metrics used by the promotion gate."""
    metrics = (result.get("baseline") or {}).get("metrics") or {}
    return {
        "macro_f1": float(metrics.get("macro_f1", 0.0)),
        "rated_0_20_accuracy": float(metrics.get("rated_0_20_accuracy", 0.0)),
    }


def energy_far_metrics(ood_report: dict[str, Any]) -> dict[str, float]:
    """Extract Energy AUROC / FPR95 / OSCR on the ``far`` final-OOD family."""
    families = (ood_report.get("families") or {}).get("energy") or {}
    far = (families.get("families") or {}).get("far") or {}
    ranking = far.get("ranking") or {}
    oscr = far.get("oscr") or {}
    return {
        "auroc": float(ranking.get("auroc", 0.0)),
        "fpr95": float(ranking.get("fpr95", 0.0)),
        "oscr": float(oscr.get("auc_ccr_fpr", 0.0)),
    }


def decide_oe_promotion(baseline_id: dict[str, float], oe_id: dict[str, float],
                        baseline_ood: dict[str, float], oe_ood: dict[str, float]) -> dict[str, Any]:
    """Apply the frozen OE promotion gate (fail-closed toward REJECT)."""
    macro_drop = baseline_id["macro_f1"] - oe_id["macro_f1"]
    rated_drop = baseline_id["rated_0_20_accuracy"] - oe_id["rated_0_20_accuracy"]
    gains = {
        "auroc": oe_ood["auroc"] - baseline_ood["auroc"],
        "fpr95": baseline_ood["fpr95"] - oe_ood["fpr95"],  # positive = lower FPR@95TPR
        "oscr": oe_ood["oscr"] - baseline_ood["oscr"],
    }
    reasons: list[str] = []
    if macro_drop > ID_DEGRADATION_TOL:
        reasons.append(f"id_macro_f1_drop={macro_drop:.4f}>{ID_DEGRADATION_TOL}")
    if rated_drop > ID_DEGRADATION_TOL:
        reasons.append(f"id_rated_acc_drop={rated_drop:.4f}>{ID_DEGRADATION_TOL}")
    improved = []
    if gains["auroc"] >= OOD_AUROC_GAIN:
        improved.append("auroc")
    if gains["fpr95"] >= OOD_FPR95_GAIN:
        improved.append("fpr95")
    if gains["oscr"] >= OOD_OSCR_GAIN:
        improved.append("oscr")
    if not improved:
        reasons.append("no_ood_gain")
    decision = "PROMOTE" if not reasons else "REJECT"
    return {
        "decision": decision,
        "id_degradation": {"macro_f1_drop": macro_drop, "rated_acc_drop": rated_drop},
        "ood_gain": gains,
        "improved": improved,
        "reasons": reasons,
    }


def build_oe_report(baseline_id: dict[str, float], oe_id: dict[str, float],
                    baseline_ood: dict[str, float], oe_ood: dict[str, float],
                    decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "oe_seed": OE_FIRST_SEED,
        "baseline_id": baseline_id,
        "oe_id": oe_id,
        "baseline_ood_energy_far": baseline_ood,
        "oe_ood_energy_far": oe_ood,
        "tolerances": {
            "id_degradation_tol": ID_DEGRADATION_TOL,
            "auroc_gain": OOD_AUROC_GAIN,
            "fpr95_gain": OOD_FPR95_GAIN,
            "oscr_gain": OOD_OSCR_GAIN,
        },
        **decision,
    }


__all__ = [
    "OE_FIRST_SEED", "OE_EXTRA_SEEDS", "CONTROLS", "ID_DEGRADATION_TOL",
    "OOD_AUROC_GAIN", "OOD_FPR95_GAIN", "OOD_OSCR_GAIN", "DECISION_PROMOTE",
    "DECISION_REJECT", "id_metrics_from_result", "energy_far_metrics",
    "decide_oe_promotion", "build_oe_report",
]
