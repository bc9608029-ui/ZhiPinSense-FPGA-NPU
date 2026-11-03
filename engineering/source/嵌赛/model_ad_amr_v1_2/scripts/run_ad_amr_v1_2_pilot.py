"""Data-ablation pilot with OOD-aware selection for AD-AMR V1.2."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from evaluation.evaluate_ad_amr_v1_2 import evaluate_v1_2, ood_channels
from scripts.export_ad_amr_v1_2_onnx import export_v1_2
from scripts.release_guard_v1_2 import assert_marker
from training.train_ad_amr_v1_2 import run_v1_2_training
from training.utils import load_yaml, save_json


def variant_config(base: dict[str, Any], variant: str, seed: int, epochs: int) -> dict[str, Any]:
    config = copy.deepcopy(base)
    config["device"] = "cuda:0"
    config["seed"] = int(seed)
    config["training"]["epochs"] = int(epochs)
    config["training"]["minimum_epochs_before_stopping"] = int(epochs)
    config["output_root"] = f"outputs/ad_amr_v1_2/pilot/{variant}_seed{seed}_e{epochs}"
    robust = config["data_robustness"]
    if variant == "legacy_distribution":
        robust["enabled"] = False
    elif variant == "single_focus":
        robust["enabled"] = True
        robust["start_weights"] = {
            "base": 0.70, "cfo_focus": 0.15, "multipath_focus": 0.15, "multi_impairment": 0.0,
        }
        robust["target_weights"] = {
            "base": 0.40, "cfo_focus": 0.30, "multipath_focus": 0.30, "multi_impairment": 0.0,
        }
    elif variant == "combined_focus":
        robust["enabled"] = True
    else:
        raise ValueError(f"unknown V1.2 data variant {variant}")
    return config


def _evaluate_focus(config: dict[str, Any], checkpoint: str, domains: list[str], samples: int) -> dict[str, Any]:
    validation = evaluate_v1_2(config, checkpoint)
    available = ood_channels(config["channel"])
    ood = {
        name: evaluate_v1_2(
            config, checkpoint, split=f"ad_amr_v1_2_validation_ood_{name}",
            channel=available[name], samples=samples,
        )
        for name in domains
    }
    base_f1 = float(validation["metrics"]["macro_f1"])
    drops = {name: base_f1 - float(report["metrics"]["macro_f1"]) for name, report in ood.items()}
    worst_ood_f1 = min(float(report["metrics"]["macro_f1"]) for report in ood.values())
    robust_score = 0.55 * float(validation["metrics"]["selection_score"]) + 0.45 * worst_ood_f1
    return {"validation": validation, "ood": ood, "ood_drops": drops,
            "max_ood_drop": max(drops.values()), "worst_ood_macro_f1": worst_ood_f1,
            "robust_selection_score": robust_score}


def main() -> int:
    bound_hash = assert_marker()
    base = load_yaml("configs/ad_amr_v1_2.yaml")
    pilot = base["pilot"]
    epochs = int(pilot["stage_a_epochs"])
    seeds = [int(value) for value in pilot["seeds"]]
    variants = [str(value) for value in pilot["variants"]]
    domains = [str(value) for value in pilot["focus_ood_domains"]]
    ood_samples = int(pilot["ood_samples"])
    stage_a = []
    for variant in variants:
        config = variant_config(base, variant, seeds[0], epochs)
        training = run_v1_2_training(config, resume=True)
        checkpoint = f"{config['output_root']}/checkpoints/best.pt"
        metrics = _evaluate_focus(config, checkpoint, domains, ood_samples)
        stage_a.append({"variant": variant, "seed": seeds[0], "checkpoint": checkpoint,
                        "training": training, **metrics})
    winner = max(stage_a, key=lambda row: (
        row["robust_selection_score"], -row["max_ood_drop"],
        row["validation"]["metrics"]["macro_f1"],
    ))
    legacy = next(row for row in stage_a if row["variant"] == "legacy_distribution")
    improvement = float(legacy["max_ood_drop"] - winner["max_ood_drop"])

    records = []
    for seed in seeds:
        config = variant_config(base, str(winner["variant"]), seed, epochs)
        training = run_v1_2_training(config, resume=True)
        checkpoint = f"{config['output_root']}/checkpoints/best.pt"
        records.append({"seed": seed, "training": training, "checkpoint": checkpoint,
                        **_evaluate_focus(config, checkpoint, domains, ood_samples)})
    export = export_v1_2(
        variant_config(base, str(winner["variant"]), seeds[0], epochs), records[0]["checkpoint"]
    )
    gates = pilot["gates"]
    pilot_pass = (
        winner["variant"] != "legacy_distribution"
        and improvement >= float(gates["min_stage_a_ood_drop_improvement"])
        and all(
            float(record["validation"]["metrics"]["macro_f1"]) >= float(gates["min_macro_f1"])
            and float(record["validation"]["metrics"]["rated_0_20_accuracy"])
            >= float(gates["min_rated_0_20_accuracy"])
            and float(record["validation"]["metrics"]["min_rated_class_accuracy"])
            >= float(gates["min_rated_class_accuracy"])
            and float(record["max_ood_drop"]) <= float(gates["max_focus_ood_macro_f1_drop"])
            for record in records
        )
        and not export["inspection"]["unexpected_operators"]
    )
    report = {
        "release_input_hash": bound_hash, "stage_a": stage_a,
        "winner_variant": winner["variant"], "stage_a_max_drop_improvement": improvement,
        "two_seed_results": records, "onnx": export, "promoted": pilot_pass,
        "selection_scope": "train/validation/OOD-validation only; test/final blind not instantiated",
    }
    output = Path("outputs/ad_amr_v1_2/pilot")
    output.mkdir(parents=True, exist_ok=True)
    save_json(report, output / "pilot_report.json")
    (output / "selected_candidate.json").write_text(json.dumps({
        "variant": winner["variant"], "promoted": pilot_pass,
        "formal_seeds": seeds, "formal_epochs": int(pilot["formal_epochs"]),
        "stage_a_max_drop_improvement": improvement,
    }, indent=2), encoding="utf-8")
    print(json.dumps({"winner": winner["variant"], "promoted": pilot_pass,
                      "stage_a_max_drop_improvement": improvement,
                      "seed_metrics": [{"seed": record["seed"],
                                        "validation": record["validation"]["metrics"],
                                        "ood_drops": record["ood_drops"]} for record in records]}, indent=2))
    print("AD_AMR_V1_2_PILOT_PASS" if pilot_pass else "AD_AMR_V1_2_PILOT_NO_GO")
    return 0 if pilot_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
