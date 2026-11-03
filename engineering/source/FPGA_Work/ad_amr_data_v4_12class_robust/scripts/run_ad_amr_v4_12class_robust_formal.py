"""Two-seed robustness formal for the promoted candidate (fail closed).

Runs only after the pilot promoted a **unique** candidate AND that candidate was
durably locked for formal (``scripts/lock_robust_formal_config.py``).  It refuses
to start unless the ``FINAL_CONFIG_APPROVED`` marker matches the current tree and
the locked config carries ``robust.final_config_approved: true``.

For each seed it fine-tunes from the frozen twelve-class best checkpoint at low LR
(the augmented channel is train-only), then evaluates the frozen validation, the
fake-int8 validation, and the six OOD domains, and evaluates the paired init
checkpoint for the improvement deltas.  The eleven frozen acceptance gates are
unchanged (``max_ood_macro_f1_drop = 0.08``); the additional minimum-improvement
gate enforces cfo_strong >= 0.0446 / multipath >= 0.0378 / multi_impairment >= 0.0522
on the two-seed mean.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from evaluation.evaluate_ad_amr_v1_1 import evaluate_v1_1, ood_channels
from scripts.export_ad_amr_v1_1_onnx import export_v1_1
from scripts.lock_robust_formal_config import MARKER, config_sha256
from scripts.release_guard_v1_1_data_v4_12class_robust import release_input_hash
from training.train_ad_amr_v4_12class_robust import run_robust_training
from training.utils import load_yaml, save_json

FORMAL_CONFIG = "configs/ad_amr_v1_1_data_v4_12class_robust_formal.yaml"
OUT_ROOT = "outputs/ad_amr_v1_1_data_v4_12class_robust/formal"


def _gate(name: str, passed: bool, values: Any) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "values": values}


def _verify_approval() -> dict[str, Any]:
    if not MARKER.is_file():
        raise RuntimeError("FINAL_CONFIG_APPROVED marker is missing; lock the candidate first")
    marker = json.loads(MARKER.read_text(encoding="utf-8"))
    if not marker.get("approved"):
        raise RuntimeError("FINAL_CONFIG_APPROVED marker is not approved")
    current_hash = release_input_hash()
    if marker.get("release_input_hash") != current_hash:
        raise RuntimeError("release inputs changed after the robustness candidate was locked")
    resolved = load_yaml(FORMAL_CONFIG)
    if not resolved.get("robust", {}).get("final_config_approved"):
        raise RuntimeError("locked robustness config has final_config_approved != true")
    if resolved.get("robust", {}).get("status") != "APPROVED_FOR_FORMAL":
        raise RuntimeError("locked robustness config status is not APPROVED_FOR_FORMAL")
    if marker.get("config_sha256") != config_sha256(resolved):
        raise RuntimeError("locked robustness config changed after approval")
    if marker.get("candidate") != resolved.get("robust", {}).get("candidate"):
        raise RuntimeError("locked robustness candidate does not match the config")
    return marker


def _formal_config(base: dict[str, Any], seed: int) -> dict[str, Any]:
    config = copy.deepcopy(base)
    formal = config["robust"]["formal"]
    config["seed"] = int(seed)
    config["device"] = "cuda:0"
    config["training"]["epochs"] = int(formal["epochs"])
    config["training"]["minimum_epochs_before_stopping"] = int(
        formal["minimum_epochs_before_stopping"]
    )
    config["training"]["learning_rate"] = float(formal["learning_rate"])
    config["output_root"] = f"{OUT_ROOT}/seed{seed}"
    return config


def main() -> int:
    marker = _verify_approval()
    base = load_yaml(FORMAL_CONFIG)
    seeds = [int(value) for value in base["robust"]["formal"]["seeds"]]
    required = int(base["acceptance"]["seeds_required"])
    if len(seeds) != required or len(set(seeds)) != required:
        raise RuntimeError("robustness formal seeds do not satisfy the frozen acceptance contract")
    focus = [str(d) for d in base["robust"]["pilot"]["focus_ood_domains"]]
    min_improvement = {
        str(k): float(v) for k, v in base["robust"]["pilot"]["min_improvement"].items()
    }
    channels = ood_channels(base["channel"])

    records: list[dict[str, Any]] = []
    for seed in seeds:
        config = _formal_config(base, seed)
        training = run_robust_training(config, resume=True)
        checkpoint = f"{config['output_root']}/checkpoints/best.pt"
        validation = evaluate_v1_1(config, checkpoint)
        quantized = evaluate_v1_1(
            config, checkpoint,
            split="ad_amr_v1_1_data_v3_12class_validation_fake_int8", fake_int8=True,
        )
        ood = {
            domain: evaluate_v1_1(
                config, checkpoint,
                split=f"ad_amr_v1_1_data_v3_12class_validation_ood_{domain}",
                channel=channel, samples=int(config["evaluation"]["ood_samples"]),
            )
            for domain, channel in channels.items()
        }
        # Paired init checkpoint (frozen twelve-class best) for the improvement delta.
        init_checkpoint = str(config["robust"]["init_checkpoint"]).format(seed=seed)
        baseline_validation = evaluate_v1_1(config, init_checkpoint)
        baseline_ood = {
            domain: evaluate_v1_1(
                config, init_checkpoint,
                split=f"ad_amr_v1_1_data_v3_12class_validation_ood_{domain}",
                channel=channel, samples=int(config["evaluation"]["ood_samples"]),
            )
            for domain, channel in channels.items()
        }
        records.append({
            "seed": seed, "training": training, "checkpoint": checkpoint,
            "validation": validation, "fake_int8": quantized, "ood": ood,
            "baseline_checkpoint": init_checkpoint,
            "baseline_validation": baseline_validation, "baseline_ood": baseline_ood,
        })

    export_config = _formal_config(base, seeds[0])
    export_config["output_root"] = f"{OUT_ROOT}/export"
    export = export_v1_1(export_config, records[0]["checkpoint"])
    threshold = base["acceptance"]["gates"]

    def mean_metric(key: str) -> float:
        return sum(float(r["validation"]["metrics"][key]) for r in records) / len(records)

    snr0 = {str(r["seed"]): r["validation"]["metrics"]["snr_0_accuracy"] for r in records}
    min_class = {
        str(r["seed"]): r["validation"]["metrics"]["min_rated_class_accuracy"] for r in records
    }
    ask_accuracy = {
        f"seed{r['seed']}_{name}": r["validation"]["metrics"]["rated_per_class_accuracy"][name]
        for r in records for name in ("OOK", "4ASK")
    }
    int8_drop = {
        str(r["seed"]): float(r["validation"]["metrics"]["accuracy"])
        - float(r["fake_int8"]["metrics"]["accuracy"]) for r in records
    }
    ood_drop = {
        f"seed{r['seed']}_{domain}": float(r["validation"]["metrics"]["macro_f1"])
        - float(report["metrics"]["macro_f1"])
        for r in records for domain, report in r["ood"].items()
    }

    improvement: dict[str, float] = {}
    improvement_detail: dict[str, dict[str, float]] = {}
    for domain in channels:
        drops = []
        for r in records:
            b_drop = float(r["baseline_validation"]["metrics"]["macro_f1"]) \
                - float(r["baseline_ood"][domain]["metrics"]["macro_f1"])
            c_drop = float(r["validation"]["metrics"]["macro_f1"]) \
                - float(r["ood"][domain]["metrics"]["macro_f1"])
            drops.append(b_drop - c_drop)
            improvement_detail.setdefault(domain, {})[str(r["seed"])] = b_drop - c_drop
        improvement[domain] = sum(drops) / len(drops)

    gates = [
        _gate("pilot_candidate_promoted_unique", marker.get("candidate") is not None, marker.get("candidate")),
        _gate("final_config_approved", True, marker.get("config_sha256")),
        _gate("two_seeds_complete", len(records) == required, len(records)),
        _gate("mean_full_macro_f1", mean_metric("macro_f1") >= float(threshold["mean_full_macro_f1"]), mean_metric("macro_f1")),
        _gate("mean_full_accuracy", mean_metric("accuracy") >= float(threshold["mean_full_accuracy"]), mean_metric("accuracy")),
        _gate("mean_rated_0_20_accuracy", mean_metric("rated_0_20_accuracy") >= float(threshold["mean_rated_0_20_accuracy"]), mean_metric("rated_0_20_accuracy")),
        _gate("mean_high_10_20_accuracy", mean_metric("high_10_20_accuracy") >= float(threshold["mean_high_10_20_accuracy"]), mean_metric("high_10_20_accuracy")),
        _gate("each_seed_snr_0_accuracy", all(float(v) >= float(threshold["each_seed_snr_0_accuracy"]) for v in snr0.values()), snr0),
        _gate("each_seed_min_rated_class_accuracy", all(float(v) >= float(threshold["each_seed_min_rated_class_accuracy"]) for v in min_class.values()), min_class),
        _gate("each_seed_new_ask_rated_accuracy", all(float(v) >= float(threshold["each_seed_new_ask_rated_accuracy"]) for v in ask_accuracy.values()), ask_accuracy),
        _gate("ood_macro_f1_drop", all(float(v) <= float(threshold["max_ood_macro_f1_drop"]) for v in ood_drop.values()), ood_drop),
        _gate("min_improvement_focus_ood", all(improvement[d] >= min_improvement[d] for d in focus), improvement),
        _gate("fake_int8_accuracy_drop", all(float(v) <= float(threshold["fake_int8_accuracy_drop"]) for v in int8_drop.values()), int8_drop),
        _gate("onnx_operator_whitelist", not export["inspection"]["unexpected_operators"], export["inspection"]),
        _gate("onnx_runtime_parity", float(export["ort_parity"]["max_abs_diff"]) <= float(threshold["onnx_max_abs_diff"]), export["ort_parity"]),
        _gate("public_and_final_blind_untouched", all(not r["validation"]["final_blind_test_accessed"] for r in records), {"public_test_accessed": False, "final_blind_test_accessed": False}),
    ]
    promoted = all(gate["pass"] for gate in gates)
    report = {
        "release_input_hash": marker.get("release_input_hash"),
        "candidate": marker.get("candidate"),
        "class_contract": base["signal"]["modulations"],
        "records": records,
        "ood_improvement": improvement,
        "ood_improvement_detail": improvement_detail,
        "export": export,
        "gates": gates,
        "promoted": promoted,
        "public_test_accessed": False,
        "final_blind_test_accessed": False,
        "deployment_status": "candidate-only; vendor NPU compile/parity and SDR gates remain",
    }
    save_json(report, f"{OUT_ROOT}/acceptance.json")
    print(json.dumps({"promoted": promoted, "gates": gates, "improvement": improvement}, indent=2))
    print("AD_AMR_V1_1_DATA_V4_12CLASS_ROBUST_FORMAL_PASS" if promoted
          else "AD_AMR_V1_1_DATA_V4_12CLASS_ROBUST_FORMAL_NO_GO")
    return 0 if promoted else 2


if __name__ == "__main__":
    raise SystemExit(main())
