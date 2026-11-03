"""Two-seed formal acceptance for the promoted RadioML-pretrained V1.1 model."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from evaluation.evaluate_ad_amr_v1_1 import evaluate_v1_1, ood_channels
from scripts.export_ad_amr_v1_1_onnx import export_v1_1
from scripts.release_guard_v1_1_data_v2 import assert_marker
from training.train_ad_amr_v1_1_data_v2 import run_data_v2_training
from training.utils import load_yaml, save_json


def _gate(name: str, passed: bool, values: Any) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "values": values}


def _formal_config(base: dict[str, Any], seed: int) -> dict[str, Any]:
    config = copy.deepcopy(base)
    formal = config["data_v2_formal"]
    config["seed"] = int(seed)
    config["training"]["epochs"] = int(formal["epochs"])
    config["training"]["minimum_epochs_before_stopping"] = int(
        formal["minimum_epochs_before_stopping"]
    )
    config["output_root"] = f"outputs/ad_amr_v1_1_data_v2/formal/seed{seed}"
    return config


def main() -> int:
    bound_hash = assert_marker()
    selected_path = Path("outputs/ad_amr_v1_1_data_v2/pilot/selected_candidate.json")
    if not selected_path.is_file():
        raise RuntimeError("data-v2 pilot selection is missing")
    selected = json.loads(selected_path.read_text(encoding="utf-8"))
    if not selected.get("promoted", False):
        raise RuntimeError("data-v2 pilot did not promote public pretraining")
    if selected.get("variant") != "radioml_pretrained":
        raise RuntimeError("unexpected data-v2 formal variant")

    base = load_yaml("configs/ad_amr_v1_1_data_v2.yaml")
    seeds = [int(value) for value in base["data_v2_formal"]["seeds"]]
    required = int(base["acceptance"]["seeds_required"])
    if len(seeds) != required or len(set(seeds)) != required:
        raise RuntimeError("data-v2 formal seeds do not satisfy the frozen acceptance contract")

    records: list[dict[str, Any]] = []
    for seed in seeds:
        config = _formal_config(base, seed)
        training = run_data_v2_training(
            config, resume=True, initialize_from_public=True
        )
        checkpoint = f"{config['output_root']}/checkpoints/best.pt"
        validation = evaluate_v1_1(config, checkpoint)
        quantized = evaluate_v1_1(
            config, checkpoint,
            split="ad_amr_v1_1_data_v2_validation_fake_int8", fake_int8=True,
        )
        ood = {
            domain: evaluate_v1_1(
                config, checkpoint,
                split=f"ad_amr_v1_1_data_v2_validation_ood_{domain}",
                channel=channel, samples=int(config["evaluation"]["ood_samples"]),
            )
            for domain, channel in ood_channels(config["channel"]).items()
        }
        records.append({
            "seed": seed, "training": training, "checkpoint": checkpoint,
            "validation": validation, "fake_int8": quantized, "ood": ood,
        })

    export_config = _formal_config(base, seeds[0])
    export_config["output_root"] = "outputs/ad_amr_v1_1_data_v2/formal/export"
    export = export_v1_1(export_config, records[0]["checkpoint"])
    threshold = base["acceptance"]["gates"]

    def mean_metric(key: str) -> float:
        return sum(float(record["validation"]["metrics"][key]) for record in records) / len(records)

    full_f1 = mean_metric("macro_f1")
    full_acc = mean_metric("accuracy")
    rated = mean_metric("rated_0_20_accuracy")
    high = mean_metric("high_10_20_accuracy")
    snr0 = {
        str(record["seed"]): record["validation"]["metrics"]["snr_0_accuracy"]
        for record in records
    }
    min_class = {
        str(record["seed"]): record["validation"]["metrics"]["min_rated_class_accuracy"]
        for record in records
    }
    int8_drop = {
        str(record["seed"]): float(record["validation"]["metrics"]["accuracy"])
        - float(record["fake_int8"]["metrics"]["accuracy"])
        for record in records
    }
    ood_drop: dict[str, float] = {}
    for record in records:
        base_f1 = float(record["validation"]["metrics"]["macro_f1"])
        for domain, report in record["ood"].items():
            ood_drop[f"seed{record['seed']}_{domain}"] = (
                base_f1 - float(report["metrics"]["macro_f1"])
            )

    gates = [
        _gate("pilot_promoted", True, selected.get("gates", {})),
        _gate("two_seeds_complete", len(records) == required, len(records)),
        _gate("mean_full_macro_f1", full_f1 >= float(threshold["mean_full_macro_f1"]), full_f1),
        _gate("mean_full_accuracy", full_acc >= float(threshold["mean_full_accuracy"]), full_acc),
        _gate("mean_rated_0_20_accuracy", rated >= float(threshold["mean_rated_0_20_accuracy"]), rated),
        _gate("mean_high_10_20_accuracy", high >= float(threshold["mean_high_10_20_accuracy"]), high),
        _gate(
            "each_seed_snr_0_accuracy",
            all(float(value) >= float(threshold["each_seed_snr_0_accuracy"])
                for value in snr0.values()), snr0,
        ),
        _gate(
            "each_seed_min_rated_class_accuracy",
            all(float(value) >= float(threshold["each_seed_min_rated_class_accuracy"])
                for value in min_class.values()), min_class,
        ),
        _gate(
            "ood_macro_f1_drop",
            all(float(value) <= float(threshold["max_ood_macro_f1_drop"])
                for value in ood_drop.values()), ood_drop,
        ),
        _gate(
            "fake_int8_accuracy_drop",
            all(float(value) <= float(threshold["fake_int8_accuracy_drop"])
                for value in int8_drop.values()), int8_drop,
        ),
        _gate(
            "onnx_operator_whitelist",
            not export["inspection"]["unexpected_operators"], export["inspection"],
        ),
        _gate(
            "onnx_runtime_parity",
            float(export["ort_parity"]["max_abs_diff"])
            <= float(threshold["onnx_max_abs_diff"]), export["ort_parity"],
        ),
        _gate(
            "public_and_final_blind_untouched",
            all(not record["validation"]["final_blind_test_accessed"] for record in records),
            {"public_test_accessed": False, "final_blind_test_accessed": False},
        ),
    ]
    promoted = all(gate["pass"] for gate in gates)
    report = {
        "release_input_hash": bound_hash,
        "variant": "radioml_pretrained",
        "records": records,
        "export": export,
        "gates": gates,
        "promoted": promoted,
        "public_test_accessed": False,
        "final_blind_test_accessed": False,
        "deployment_status": (
            "candidate-only; vendor NPU compile, numeric parity, and SDR validation remain external gates"
        ),
    }
    save_json(report, "outputs/ad_amr_v1_1_data_v2/formal/acceptance.json")
    print(json.dumps({"promoted": promoted, "gates": gates}, indent=2))
    print("AD_AMR_V1_1_DATA_V2_FORMAL_PASS" if promoted
          else "AD_AMR_V1_1_DATA_V2_FORMAL_NO_GO")
    return 0 if promoted else 2


if __name__ == "__main__":
    raise SystemExit(main())
