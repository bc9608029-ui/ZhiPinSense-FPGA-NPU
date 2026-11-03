"""Shared OOD (out-of-distribution / open-set) framework.

All scores are *anomaly* scores: higher means more likely OOD, and the decision
rule is ``UNKNOWN if score > threshold``.  This keeps MSP / Entropy / MaxLogit /
Energy / Mahalanobis / OpenMax on one common footing.
"""

from ood.energy import energy_score
from ood.scores import compute_scores, energy_anomaly, entropy_anomaly, max_logit_anomaly, msp_anomaly
from ood.metrics import (
    auroc,
    aupr_in,
    aupr_out,
    bootstrap_ci,
    fpr95,
    oscr,
    ranking_metrics,
)
from ood.thresholds import (
    OOD_WORKING_POINTS,
    select_thresholds,
    decision_at_thresholds,
)
from ood.calibration import temperature_scale, calibrate_temperature

__all__ = [
    "energy_score", "compute_scores", "energy_anomaly", "entropy_anomaly",
    "max_logit_anomaly", "msp_anomaly",
    "auroc", "aupr_in", "aupr_out", "bootstrap_ci", "fpr95", "oscr", "ranking_metrics",
    "OOD_WORKING_POINTS", "select_thresholds", "decision_at_thresholds",
    "temperature_scale", "calibrate_temperature",
]
