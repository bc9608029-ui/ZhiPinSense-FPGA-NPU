"""Leakage-safe staged AD-AMR pilot with paired frozen-V2 promotion gates."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import yaml

from evaluation.evaluate_ad_amr_pilot import evaluate_paired, ood_channel_configs
from scripts.export_ad_amr_onnx import export_ad_amr
from scripts.release_guard import assert_preflight_marker
from training.train_ad_amr import run_training
from training.utils import load_yaml, save_json

MARKER_PASS = "AD_AMR_V1_PILOT_PASS"
MARKER_NO_GO = "AD_AMR_V1_PILOT_NO_GO"


def _pilot_config(base: dict[str, Any], variant: str, seed: int, epochs: int) -> dict[str, Any]:
    cfg = yaml.safe_load(yaml.safe_dump(base))
    cfg["device"] = "cuda:0"
    cfg["seed"] = int(seed)
    cfg["training"]["epochs"] = int(epochs)
    cfg["training"]["loss"]["variant"] = variant
    cfg["training"]["minimum_epochs_before_stopping"] = int(epochs)
    cfg["output_root"] = f"outputs/ad_amr_v1/pilot/{variant}_seed{seed}_e{epochs}"
    return cfg


def _train(stage: str, cfg: dict[str, Any]) -> dict[str, Any]:
    variant = str(cfg["training"]["loss"]["variant"])
    seed = int(cfg["seed"])
    epochs = int(cfg["training"]["epochs"])
    try:
        resume = (Path(cfg["output_root"]) / "checkpoints/last.pt").exists()
        result = run_training(cfg, resume=resume)
        values = [result["best_validation_macro_f1"], result["best_validation_accuracy"]]
        if not all(math.isfinite(float(v)) for v in values):
            raise RuntimeError("training summary contains NaN/Inf")
        return {
            "stage": stage, "variant": variant, "seed": seed, "epochs": epochs,
            "status": "ok", "best_val_macro_f1": result["best_validation_macro_f1"],
            "best_val_accuracy": result["best_validation_accuracy"],
            "best_epoch": result["best_epoch"],
            "checkpoint": f"{cfg['output_root']}/checkpoints/best.pt",
        }
    except Exception as exc:
        return {
            "stage": stage, "variant": variant, "seed": seed, "epochs": epochs,
            "status": "failed", "error": f"{type(exc).__name__}: {exc}",
        }


def _gate(name: str, passed: bool, values: Any) -> dict[str, Any]:
    return {"name": name, "pass": bool(passed), "values": values}


def _mean(records: list[dict[str, Any]], side: str, metric: str) -> float:
    return sum(float(record["paired"][side][metric]) for record in records) / len(records)


def decide_gates(records: list[dict[str, Any]], thresholds: dict[str, float],
                 training_complete: bool, onnx_ok: bool) -> list[dict[str, Any]]:
    """Pure gate function kept testable with synthetic metric records."""
    gates = [
        _gate("stage_a_and_b_complete", training_complete, {"complete": training_complete}),
        _gate("two_seed_paired_evaluations", len(records) == 2, {"count": len(records)}),
    ]
    if len(records) != 2:
        for name in (
            "mean_macro_f1_gain", "mean_accuracy_gain", "per_seed_macro_f1_floor",
            "per_class_regression_floor", "snr_0_10_20_regression_floor",
            "accuracy_0_10db_gain", "qam_mean_non_regression",
            "ood_domain_macro_f1_floor",
        ):
            gates.append(_gate(name, False, "missing paired results"))
    else:
        candidate_f1 = _mean(records, "candidate", "macro_f1")
        v2_f1 = _mean(records, "v2", "macro_f1")
        candidate_acc = _mean(records, "candidate", "accuracy")
        v2_acc = _mean(records, "v2", "accuracy")
        f1_gain = candidate_f1 - v2_f1
        acc_gain = candidate_acc - v2_acc
        gates.append(_gate("mean_macro_f1_gain", f1_gain >= thresholds["mean_macro_f1_gain"],
                           {"candidate": candidate_f1, "v2": v2_f1, "gain": f1_gain}))
        gates.append(_gate("mean_accuracy_gain", acc_gain >= thresholds["mean_accuracy_gain"],
                           {"candidate": candidate_acc, "v2": v2_acc, "gain": acc_gain}))

        seed_f1 = {
            str(r["seed"]): float(r["paired"]["candidate"]["macro_f1"])
            - float(r["paired"]["v2"]["macro_f1"]) for r in records
        }
        gates.append(_gate(
            "per_seed_macro_f1_floor",
            all(v >= -thresholds["per_seed_macro_f1_regression"] for v in seed_f1.values()),
            seed_f1,
        ))

        class_deltas: dict[str, float] = {}
        for r in records:
            for name, value in r["paired"]["candidate"]["per_class_accuracy"].items():
                class_deltas[f"seed{r['seed']}_{name}"] = float(value) - float(
                    r["paired"]["v2"]["per_class_accuracy"][name]
                )
        gates.append(_gate(
            "per_class_regression_floor",
            all(v >= -thresholds["per_class_regression"] for v in class_deltas.values()),
            class_deltas,
        ))

        snr_deltas: dict[str, float] = {}
        for r in records:
            for snr in ("0", "10", "20"):
                snr_deltas[f"seed{r['seed']}_snr{snr}"] = float(
                    r["paired"]["candidate"]["per_snr_accuracy"][snr]
                ) - float(r["paired"]["v2"]["per_snr_accuracy"][snr])
        gates.append(_gate(
            "snr_0_10_20_regression_floor",
            all(v >= -thresholds["snr_0_10_20_regression"] for v in snr_deltas.values()),
            snr_deltas,
        ))

        candidate_mid = _mean(records, "candidate", "accuracy_0_10db")
        v2_mid = _mean(records, "v2", "accuracy_0_10db")
        mid_gain = candidate_mid - v2_mid
        gates.append(_gate("accuracy_0_10db_gain", mid_gain >= thresholds["accuracy_0_10db_gain"],
                           {"candidate": candidate_mid, "v2": v2_mid, "gain": mid_gain}))

        candidate_qam = _mean(records, "candidate", "qam_mean_accuracy")
        v2_qam = _mean(records, "v2", "qam_mean_accuracy")
        qam_delta = candidate_qam - v2_qam
        gates.append(_gate("qam_mean_non_regression", qam_delta >= -thresholds["qam_mean_regression"],
                           {"candidate": candidate_qam, "v2": v2_qam, "delta": qam_delta}))

        ood_deltas: dict[str, float] = {}
        for r in records:
            for domain, report in r["ood"].items():
                ood_deltas[f"seed{r['seed']}_{domain}"] = float(
                    report["candidate"]["macro_f1"]
                ) - float(report["v2"]["macro_f1"])
        gates.append(_gate(
            "ood_domain_macro_f1_floor",
            bool(ood_deltas) and all(
                v >= -thresholds["ood_domain_macro_f1_regression"] for v in ood_deltas.values()
            ),
            ood_deltas,
        ))

    finite = True

    def visit(value: Any) -> None:
        nonlocal finite
        if isinstance(value, float) and not math.isfinite(value):
            finite = False
        elif isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(records)
    gates.append(_gate("finite_complete_metrics", finite, {"finite": finite}))
    gates.append(_gate("test_and_blind_untouched", all(
        not r["paired"].get("final_blind_test_accessed", True) for r in records
    ), {"accessed": ["ad_amr_train", "ad_amr_validation", "ad_amr_validation_ood_*"]}))
    gates.append(_gate("onnx_runtime_parity", onnx_ok, {"status_ok": onnx_ok}))
    return gates


def main() -> int:
    assert_preflight_marker()
    base = load_yaml("configs/ad_amr_v1.yaml")
    pilot = base["pilot"]
    stage_a_epochs = int(pilot["stage_a_epochs"])
    stage_b_epochs = int(pilot["stage_b_epochs"])
    seeds = [int(v) for v in pilot["seeds"]]
    if len(seeds) != 2:
        raise RuntimeError("pilot requires exactly two independent seeds")

    stage_a = [_train("A", _pilot_config(base, v, seeds[0], stage_a_epochs)) for v in ("P0", "P1")]
    complete_a = [row for row in stage_a if row["status"] == "ok"]
    winner = max(complete_a, key=lambda row: row["best_val_macro_f1"]) if len(complete_a) == 2 else None

    stage_b: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    if winner is not None:
        for seed in seeds:
            cfg = _pilot_config(base, winner["variant"], seed, stage_b_epochs)
            trained = _train("B", cfg)
            stage_b.append(trained)
            if trained["status"] != "ok":
                continue
            paired = evaluate_paired(cfg, trained["checkpoint"], split="ad_amr_validation")
            ood = {}
            for domain, channel_cfg in ood_channel_configs(cfg["channel"]).items():
                ood[domain] = evaluate_paired(
                    cfg,
                    trained["checkpoint"],
                    split=f"ad_amr_validation_ood_{domain}",
                    channel_config=channel_cfg,
                    samples=int(pilot["ood_samples"]),
                )
            records.append({"seed": seed, "checkpoint": trained["checkpoint"],
                            "paired": paired, "ood": ood})

    onnx_report: dict[str, Any] | None = None
    onnx_ok = False
    if records and winner is not None:
        cfg = _pilot_config(base, winner["variant"], seeds[0], stage_b_epochs)
        onnx_report = export_ad_amr(cfg, records[0]["checkpoint"])
        onnx_ok = onnx_report["ort_parity"]["status"] == "ok"

    training_complete = len(complete_a) == 2 and len(stage_b) == 2 and all(
        row["status"] == "ok" for row in stage_b
    )
    thresholds = {name: float(value) for name, value in pilot["gates"].items()}
    gates = decide_gates(records, thresholds, training_complete, onnx_ok)
    passed = all(gate["pass"] for gate in gates)
    report = {
        "stage_a": stage_a,
        "stage_b": stage_b,
        "winner_variant": winner["variant"] if winner else None,
        "paired_seed_results": records,
        "thresholds": thresholds,
        "gates": gates,
        "onnx": onnx_report,
        "promoted": passed,
        "marker": MARKER_PASS if passed else MARKER_NO_GO,
        "selection_scope": "train + validation only; test/final blind never instantiated",
    }
    output = Path("outputs/ad_amr_v1/pilot")
    output.mkdir(parents=True, exist_ok=True)
    save_json(report, output / "pilot_report.json")
    selected = {
        "selected_variant": winner["variant"] if winner else None,
        "promoted": passed,
        "pilot_report": str(output / "pilot_report.json"),
        "checkpoints": [r["checkpoint"] for r in records],
        "selection_scope": report["selection_scope"],
    }
    (output / "selected_candidate.yaml").write_text(
        yaml.safe_dump(selected, sort_keys=False), encoding="utf-8", newline="\n"
    )
    print(json.dumps({"winner": report["winner_variant"], "promoted": passed,
                      "gates": gates}, indent=2))
    print(report["marker"])
    return 0 if passed else 2


if __name__ == "__main__":
    sys.exit(main())
