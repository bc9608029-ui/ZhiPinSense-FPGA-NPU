"""Data-v4 robustness pilot: baseline vs candidate A/B/C (fail closed).

Compares the original twelve-class seed2026 checkpoint (eval-only baseline) against
three augmentation candidates, each a low-LR fine-tune from the same best.pt with a
different ``robust.train_channel``:

  * A — CFO tail only
  * B — multipath tail + composite
  * C — CFO tail + multipath tail + composite

Selection is fail-closed and requires a **unique** qualifying candidate:

  * every focus OOD domain improves by at least ``robust.pilot.min_improvement``
    (so its macro-F1 drop returns within the 0.08 formal gate);
  * clean validation macro-F1 / rated-0-20 / SNR-0 / min-rated-class regress by no
    more than ``robust.pilot.regression_bounds``;
  * fake-int8 accuracy drop stays within the frozen gate;
  * the ONNX export keeps the unchanged operator whitelist and ORT parity.

The frozen evaluation always uses the same validation / OOD records and the frozen
``config["channel"]``; the augmented channel is confined to the train split.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from evaluation.evaluate_ad_amr_v1_1 import evaluate_v1_1, ood_channels
from scripts.export_ad_amr_v1_1_onnx import export_v1_1
from scripts.release_guard_v1_1_data_v4_12class_robust import assert_robust_marker
from training.train_ad_amr_v4_12class_robust import run_robust_training
from training.utils import load_yaml, save_json

CANDIDATE_CONFIGS = {
    "A": "configs/ad_amr_v1_1_data_v4_12class_robust_pilot_A.yaml",
    "B": "configs/ad_amr_v1_1_data_v4_12class_robust_pilot_B.yaml",
    "C": "configs/ad_amr_v1_1_data_v4_12class_robust_pilot_C.yaml",
}


def _pilot_config(candidate: str) -> dict[str, Any]:
    config = load_yaml(CANDIDATE_CONFIGS[candidate])
    pilot = config["robust"]["pilot"]
    seed = int(pilot["seed"])
    epochs = int(pilot["epochs"])
    lr = float(pilot["learning_rate"])
    config["device"] = "cuda:0"
    config["seed"] = seed
    config["training"]["epochs"] = epochs
    config["training"]["minimum_epochs_before_stopping"] = epochs
    config["training"]["learning_rate"] = lr
    config["output_root"] = (
        f"outputs/ad_amr_v1_1_data_v4_12class_robust/pilot/candidate_{candidate}_seed{seed}_e{epochs}"
    )
    return config


def _evaluate_focus(config: dict[str, Any], checkpoint: str,
                    domains: list[str]) -> dict[str, dict[str, Any]]:
    channels = ood_channels(config["channel"])
    return {
        domain: evaluate_v1_1(
            config, checkpoint,
            split=f"ad_amr_v1_1_data_v3_12class_validation_ood_{domain}",
            channel=channels[domain], samples=int(config["evaluation"]["ood_samples"]),
        )
        for domain in domains
    }


def main() -> int:
    bound_hash = assert_robust_marker()
    base = load_yaml("configs/ad_amr_v1_1_data_v4_12class_robust.yaml")
    pilot_cfg = base["robust"]["pilot"]
    seed = int(pilot_cfg["seed"])
    focus = [str(d) for d in pilot_cfg["focus_ood_domains"]]
    min_improvement = {str(k): float(v) for k, v in pilot_cfg["min_improvement"].items()}
    regression = {str(k): float(v) for k, v in pilot_cfg["regression_bounds"].items()}
    int8_gate = float(base["acceptance"]["gates"]["fake_int8_accuracy_drop"])

    # Baseline: the original twelve-class seed best.pt, evaluated on the frozen
    # validation + focus OOD records (no retrain).
    baseline_config = load_yaml("configs/ad_amr_v1_1_data_v3_12class.yaml")
    baseline_config["seed"] = seed
    baseline_checkpoint = str(base["robust"]["init_checkpoint"]).format(seed=seed)
    baseline_validation = evaluate_v1_1(baseline_config, baseline_checkpoint)
    baseline_ood = _evaluate_focus(baseline_config, baseline_checkpoint, focus)
    baseline_metrics = baseline_validation["metrics"]

    results: dict[str, Any] = {}
    for candidate in [str(c) for c in pilot_cfg["candidates"]]:
        config = _pilot_config(candidate)
        trained = run_robust_training(config, resume=True)
        checkpoint = f"{config['output_root']}/checkpoints/best.pt"
        validation = evaluate_v1_1(config, checkpoint)
        quantized = evaluate_v1_1(
            config, checkpoint,
            split="ad_amr_v1_1_data_v3_12class_validation_fake_int8", fake_int8=True,
        )
        ood = _evaluate_focus(config, checkpoint, focus)
        results[candidate] = {
            "training": trained, "checkpoint": checkpoint,
            "validation": validation, "fake_int8": quantized, "ood": ood,
        }

    # Compute deltas and OOD improvements against the paired baseline.
    comparisons: dict[str, Any] = {}
    for candidate, res in results.items():
        val = res["validation"]["metrics"]
        deltas = {
            "macro_f1": float(val["macro_f1"]) - float(baseline_metrics["macro_f1"]),
            "rated_0_20_accuracy": float(val["rated_0_20_accuracy"]) - float(baseline_metrics["rated_0_20_accuracy"]),
            "snr_0_accuracy": float(val["snr_0_accuracy"]) - float(baseline_metrics["snr_0_accuracy"]),
            "min_rated_class_accuracy": float(val["min_rated_class_accuracy"]) - float(baseline_metrics["min_rated_class_accuracy"]),
        }
        improvement: dict[str, float] = {}
        drops: dict[str, dict[str, float]] = {}
        for domain in focus:
            b_drop = float(baseline_metrics["macro_f1"]) - float(baseline_ood[domain]["metrics"]["macro_f1"])
            c_drop = float(val["macro_f1"]) - float(res["ood"][domain]["metrics"]["macro_f1"])
            improvement[domain] = b_drop - c_drop
            drops[domain] = {"baseline_drop": b_drop, "candidate_drop": c_drop}
        int8_drop = float(val["accuracy"]) - float(res["fake_int8"]["metrics"]["accuracy"])
        comparisons[candidate] = {
            "deltas": deltas, "ood_improvement": improvement, "ood_drops": drops,
            "fake_int8_accuracy_drop": int8_drop,
        }

    # Hard selection gates per candidate.
    gate_report: dict[str, Any] = {}
    for candidate, comp in comparisons.items():
        gates: dict[str, Any] = {
            "all_focus_ood_improved": all(comp["ood_improvement"][d] >= min_improvement[d] for d in focus),
            "macro_f1_non_regression": comp["deltas"]["macro_f1"] >= -regression["macro_f1"],
            "rated_0_20_non_regression": comp["deltas"]["rated_0_20_accuracy"] >= -regression["rated_0_20_accuracy"],
            "snr_0_non_regression": comp["deltas"]["snr_0_accuracy"] >= -regression["snr_0_accuracy"],
            "min_rated_class_non_regression": comp["deltas"]["min_rated_class_accuracy"] >= -regression["min_rated_class_accuracy"],
            "fake_int8_within_gate": comp["fake_int8_accuracy_drop"] <= int8_gate,
        }
        gates["qualified"] = all(gates.values())
        gate_report[candidate] = gates

    # Verify the unchanged ONNX operator whitelist + ORT parity once (structure shared).
    export_config = _pilot_config("C")
    export = export_v1_1(export_config, results["C"]["checkpoint"])
    onnx_ok = (
        not export["inspection"]["unexpected_operators"]
        and export["ort_parity"]["status"] == "ok"
    )

    qualified = [c for c, g in gate_report.items() if g["qualified"] and onnx_ok]
    promoted = len(qualified) == 1
    selected = qualified[0] if promoted else None

    out = Path("outputs/ad_amr_v1_1_data_v4_12class_robust/pilot")
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "release_input_hash": bound_hash,
        "seed": seed,
        "baseline_checkpoint": baseline_checkpoint,
        "baseline_validation_macro_f1": baseline_metrics["macro_f1"],
        "focus_ood_domains": focus,
        "min_improvement": min_improvement,
        "regression_bounds": regression,
        "onnx_operator_whitelist_ok": onnx_ok,
        "onnx_operators": export["inspection"]["op_types"],
        "comparisons": comparisons,
        "gates": gate_report,
        "promoted": promoted,
        "selected_candidate": selected,
        "public_test_accessed": False,
        "final_blind_test_accessed": False,
    }
    save_json(report, out / "pilot_report.json")
    if promoted:
        save_json({
            "candidate": selected,
            "promoted": True,
            "checkpoint": results[selected]["checkpoint"],
            "train_channel_sha256": results[selected]["training"]["train_channel_sha256"],
            "gates": gate_report[selected],
            "comparison": comparisons[selected],
        }, out / "selected_candidate.json")

    print(json.dumps({
        "promoted": promoted, "selected": selected, "qualified": qualified,
        "gates": gate_report, "onnx_ok": onnx_ok,
    }, indent=2))
    if not promoted:
        print("AD_AMR_V1_1_DATA_V4_12CLASS_ROBUST_PILOT_NO_GO: "
              f"qualified={qualified} (a unique candidate is required)")
        return 2
    print("AD_AMR_V1_1_DATA_V4_12CLASS_ROBUST_PILOT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
