"""Thirty-epoch, two-seed validation-only V1.1 pilot."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from evaluation.evaluate_ad_amr_v1_1 import evaluate_v1_1, ood_channels
from scripts.export_ad_amr_v1_1_onnx import export_v1_1
from scripts.release_guard_v1_1 import assert_marker
from training.train_ad_amr_v1_1 import run_v1_1_training
from training.utils import load_yaml, save_json


def variant_config(base: dict[str, Any], variant: str, seed: int, epochs: int) -> dict[str, Any]:
    cfg = copy.deepcopy(base)
    cfg["device"] = "cuda:0"
    cfg["seed"] = int(seed)
    cfg["training"]["epochs"] = int(epochs)
    cfg["training"]["minimum_epochs_before_stopping"] = int(epochs)
    cfg["output_root"] = f"outputs/ad_amr_v1_1/pilot/{variant}_seed{seed}_e{epochs}"
    distill = cfg["training"]["distillation"]
    if variant == "student_only":
        distill["enabled"] = False
    elif variant == "v1_distill":
        distill.update({"enabled": True, "v2_weight": 0.0, "v1_weight": 0.30})
    elif variant == "dual_distill":
        distill.update({"enabled": True, "v2_weight": 0.15, "v1_weight": 0.25})
    else:
        raise ValueError(f"unknown V1.1 pilot variant {variant}")
    return cfg


def main() -> int:
    bound_hash = assert_marker()
    base = load_yaml("configs/ad_amr_v1_1.yaml")
    pilot = base["pilot"]
    epochs = int(pilot["stage_a_epochs"])
    seeds = [int(v) for v in pilot["seeds"]]
    variants = [str(v) for v in pilot["variants"]]
    stage_a = []
    for variant in variants:
        cfg = variant_config(base, variant, seeds[0], epochs)
        result = run_v1_1_training(cfg, resume=True)
        stage_a.append({
            "variant": variant, "seed": seeds[0], "checkpoint": f"{cfg['output_root']}/checkpoints/best.pt",
            "best_epoch": result["best_epoch"], "selection_score": result["best_selection_score"],
            "macro_f1": result["best_validation_macro_f1"],
            "rated_0_20_accuracy": result["best_validation_rated_0_20_accuracy"],
        })
    winner = max(stage_a, key=lambda row: (row["selection_score"], row["macro_f1"]))
    records = []
    for seed in seeds:
        cfg = variant_config(base, winner["variant"], seed, epochs)
        result = run_v1_1_training(cfg, resume=True)
        checkpoint = f"{cfg['output_root']}/checkpoints/best.pt"
        validation = evaluate_v1_1(cfg, checkpoint)
        records.append({"seed": seed, "training": result, "validation": validation,
                        "checkpoint": checkpoint})
    export = export_v1_1(variant_config(base, winner["variant"], seeds[0], epochs), records[0]["checkpoint"])
    # Pilot is a sanity/performance gate, not the final target gate.
    pilot_pass = all(
        record["validation"]["metrics"]["macro_f1"] >= 0.60
        and record["validation"]["metrics"]["rated_0_20_accuracy"] >= 0.80
        and record["validation"]["metrics"]["min_rated_class_accuracy"] >= 0.45
        for record in records
    ) and not export["inspection"]["unexpected_operators"]
    report = {
        "release_input_hash": bound_hash, "stage_a": stage_a,
        "winner_variant": winner["variant"], "two_seed_results": records,
        "onnx": export, "promoted": pilot_pass,
        "selection_scope": "train/validation only; test/final blind not instantiated",
    }
    output = Path("outputs/ad_amr_v1_1/pilot")
    output.mkdir(parents=True, exist_ok=True)
    save_json(report, output / "pilot_report.json")
    (output / "selected_candidate.json").write_text(json.dumps({
        "variant": winner["variant"], "promoted": pilot_pass,
        "formal_seeds": seeds, "formal_epochs": int(pilot["formal_epochs"]),
    }, indent=2), encoding="utf-8")
    print(json.dumps({"winner": winner["variant"], "promoted": pilot_pass,
                      "seed_metrics": [{"seed": r["seed"], **r["validation"]["metrics"]}
                                       for r in records]}, indent=2))
    print("AD_AMR_V1_1_PILOT_PASS" if pilot_pass else "AD_AMR_V1_1_PILOT_NO_GO")
    return 0 if pilot_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
