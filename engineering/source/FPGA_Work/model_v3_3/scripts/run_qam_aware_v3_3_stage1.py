"""Run the V3.3 Stage-1 ablation (A0-A3) and freeze a winner through the pilot.

Thin CLI wrapper over the training, narrow-search and selection modules so the
AutoDL shell can call a single command for the whole pilot:

    1. Stage-1 ablation (A0-A3, two selection seeds, validation + OOD);
    2. preliminary selection — name the winning *mechanism* and check the
       preliminary improvement threshold (A0 win or below-threshold stops here);
    3. narrow search on the actual winning mechanism (if enabled and the trained
       winner cleared the preliminary threshold) — 8 trials x 6 epochs, best
       re-confirmed at the full ablation epoch count on both seeds;
    4. final selection — compare the untuned winner against the tuned candidate
       (the tuned result is kept only if it actually improves) and apply the
       full pilot hard gates;
    5. freeze the truly winning model/training config into ``selected_candidate``
       (``.yaml`` + ``.json``).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json

import yaml

from training.narrow_search_v3_3 import run_narrow_search
from training.select_qam_aware_v3_3_candidate import select_candidate, write_candidate
from training.train_qam_aware_v3_3_stage1 import run_stage1
from training.utils import resolve_project_path

ABLATION_SUMMARY = "outputs/qam_aware_v3_3/ablation/ablation_summary.json"


def _pilot_gates(pilot: dict) -> dict:
    return {
        "maximum_ood_regression": float(pilot.get("maximum_ood_regression", 0.01)),
        "maximum_per_class_accuracy_drop": float(pilot.get("maximum_per_class_accuracy_drop", 0.03)),
        "maximum_fpga_sim_accuracy_gap": float(pilot.get("maximum_fpga_sim_accuracy_gap", 0.03)),
        "maximum_fpga_sim_macro_f1_gap": float(pilot.get("maximum_fpga_sim_macro_f1_gap", 0.03)),
    }


def _should_run_narrow_search(prelim: dict, narrow: dict) -> bool:
    if not narrow.get("enabled", False):
        return False
    if not prelim.get("winner_trained", False):
        return False
    improvement = prelim.get("improvement_over_a0")
    if improvement is None:
        return False
    threshold = float(prelim.get("minimum_improvement_threshold", 0.0))
    return float(improvement) >= threshold


def run_stage1_and_select(
    ablation_path: str = "configs/qam_aware_v3_3_stage1.yaml",
    out: str = "outputs/qam_aware_v3_3/formal/selected_candidate.yaml",
) -> dict:
    spec = yaml.safe_load(resolve_project_path(ablation_path).read_text(encoding="utf-8"))
    pilot = spec.get("pilot", {}) or {}
    narrow = spec.get("narrow_search", {}) or {}
    threshold = float(pilot.get("minimum_improvement_threshold", 0.0))
    pilot_gates = _pilot_gates(pilot)

    summary = run_stage1(ablation_path)

    prelim = select_candidate(
        summary,
        minimum_improvement_threshold=threshold,
        pilot_gates=pilot_gates,
    )

    tuned = None
    if _should_run_narrow_search(prelim, narrow):
        tuned = run_narrow_search(
            ablation_path,
            winner_variant=prelim["selected_variant"],
            winner_model=prelim["model"],
            winner_training=prelim["training"],
        )

    if tuned is not None:
        final_summary = copy.deepcopy(summary)
        final_summary["variants"] = list(final_summary.get("variants", [])) + [tuned]
        candidate = select_candidate(
            final_summary,
            minimum_improvement_threshold=threshold,
            pilot_gates=pilot_gates,
        )
    else:
        candidate = prelim

    summary_file = resolve_project_path(ABLATION_SUMMARY)
    candidate["frozen_at_ablation_summary_sha256"] = hashlib.sha256(summary_file.read_bytes()).hexdigest()
    candidate["narrow_search_ran"] = tuned is not None
    if tuned is not None:
        candidate["narrow_search_base_variant"] = tuned["base_variant"]
    write_candidate(candidate, out)

    return {
        "ablation": "completed",
        "narrow_search_ran": tuned is not None,
        "selected_candidate": candidate,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_3_stage1.yaml")
    parser.add_argument("--out", default="outputs/qam_aware_v3_3/formal/selected_candidate.yaml")
    args = parser.parse_args()
    print(json.dumps(run_stage1_and_select(args.config, args.out), indent=2))


if __name__ == "__main__":
    main()
