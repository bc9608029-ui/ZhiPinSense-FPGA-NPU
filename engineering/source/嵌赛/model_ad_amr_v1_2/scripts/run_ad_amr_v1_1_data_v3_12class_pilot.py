"""Paired scratch-vs-public-initialized pilot for the twelve-class target."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from evaluation.evaluate_ad_amr_v1_1 import evaluate_v1_1, ood_channels
from scripts.export_ad_amr_v1_1_onnx import export_v1_1
from scripts.release_guard_v1_1_data_v3_12class import assert_marker
from training.train_ad_amr_v1_1_data_v3_12class import run_data_v3_training
from training.utils import load_yaml, save_json


def _variant_config(base: dict[str, Any], variant: str) -> dict[str, Any]:
    config = copy.deepcopy(base)
    pilot = config["data_v3_pilot"]
    seed, epochs = int(pilot["seed"]), int(pilot["epochs"])
    config["device"] = "cuda:0"
    config["seed"] = seed
    config["training"]["epochs"] = epochs
    config["training"]["minimum_epochs_before_stopping"] = epochs
    config["output_root"] = (
        f"outputs/ad_amr_v1_1_data_v3_12class/pilot/{variant}_seed{seed}_e{epochs}"
    )
    return config


def _evaluate(config: dict[str, Any], checkpoint: str) -> dict[str, Any]:
    validation = evaluate_v1_1(config, checkpoint)
    channels = ood_channels(config["channel"])
    focus = {}
    for domain in config["data_v3_pilot"]["focus_ood_domains"]:
        focus[str(domain)] = evaluate_v1_1(
            config, checkpoint,
            split=f"ad_amr_v1_1_data_v3_12class_validation_ood_{domain}",
            channel=channels[str(domain)], samples=int(config["evaluation"]["ood_samples"]),
        )["metrics"]["macro_f1"]
    return {"validation": validation, "focus_ood_macro_f1": focus}


def main() -> int:
    bound_hash = assert_marker()
    base = load_yaml("configs/ad_amr_v1_1_data_v3_12class.yaml")
    results: dict[str, Any] = {}
    for variant in base["data_v3_pilot"]["variants"]:
        variant = str(variant)
        if variant not in {"scratch", "radioml_pretrained"}:
            raise RuntimeError(f"unsupported twelve-class pilot variant {variant}")
        config = _variant_config(base, variant)
        trained = run_data_v3_training(
            config, resume=True, initialize_from_public=variant == "radioml_pretrained"
        )
        checkpoint = f"{config['output_root']}/checkpoints/best.pt"
        results[variant] = {
            "training": trained, "checkpoint": checkpoint, **_evaluate(config, checkpoint),
        }

    scratch, candidate = results["scratch"], results["radioml_pretrained"]
    baseline = scratch["validation"]["metrics"]
    current = candidate["validation"]["metrics"]
    gate_config = base["data_v3_pilot"]["gates"]
    deltas = {
        "macro_f1": current["macro_f1"] - baseline["macro_f1"],
        "rated_0_20_accuracy": current["rated_0_20_accuracy"] - baseline["rated_0_20_accuracy"],
        "snr_0_accuracy": current["snr_0_accuracy"] - baseline["snr_0_accuracy"],
        "min_rated_class_accuracy": (
            current["min_rated_class_accuracy"] - baseline["min_rated_class_accuracy"]
        ),
        "focus_ood": {
            domain: candidate["focus_ood_macro_f1"][domain]
            - scratch["focus_ood_macro_f1"][domain]
            for domain in scratch["focus_ood_macro_f1"]
        },
    }
    gates = {
        "macro_f1_gain": deltas["macro_f1"] >= float(gate_config["min_macro_f1_gain"]),
        "rated_0_20_non_regression": (
            deltas["rated_0_20_accuracy"] >= float(gate_config["min_rated_0_20_gain"])
        ),
        "snr_0_non_regression": deltas["snr_0_accuracy"] >= float(gate_config["min_snr_0_gain"]),
        "min_rated_class_non_regression": (
            deltas["min_rated_class_accuracy"] >= float(gate_config["min_rated_class_delta"])
        ),
        "focus_ood_non_regression": all(
            value >= -float(gate_config["max_focus_ood_drop_increase"])
            for value in deltas["focus_ood"].values()
        ),
    }
    export = export_v1_1(_variant_config(base, "radioml_pretrained"), candidate["checkpoint"])
    gates["onnx_operator_whitelist"] = not export["inspection"]["unexpected_operators"]
    gates["onnx_runtime_parity"] = export["ort_parity"]["status"] == "ok"
    promoted = all(gates.values())
    output = Path("outputs/ad_amr_v1_1_data_v3_12class/pilot")
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "release_input_hash": bound_hash, "promoted": promoted, "gates": gates,
        "deltas_vs_paired_scratch": deltas, "results": results, "onnx": export,
        "public_test_accessed": False, "final_blind_test_accessed": False,
    }
    save_json(report, output / "pilot_report.json")
    save_json({
        "variant": "radioml_pretrained", "promoted": promoted,
        "checkpoint": candidate["checkpoint"], "gates": gates,
    }, output / "selected_candidate.json")
    print(json.dumps({"promoted": promoted, "gates": gates, "deltas": deltas}, indent=2))
    print("AD_AMR_V1_1_DATA_V3_12CLASS_PILOT_PASS" if promoted
          else "AD_AMR_V1_1_DATA_V3_12CLASS_PILOT_NO_GO")
    return 0 if promoted else 2


if __name__ == "__main__":
    raise SystemExit(main())
