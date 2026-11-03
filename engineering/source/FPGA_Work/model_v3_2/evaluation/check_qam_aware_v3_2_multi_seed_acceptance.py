"""Multi-seed promotion gate for V3.2.

The three-seed run must not be cherry-picked, so the gate applies a fixed rule:

* **Mean improvement gates** — the three-seed MEAN of accuracy, macro-F1 and QAM
  mean must each clear the improvement bar (``minimum_*_gain``), so no single
  lucky seed can carry the promotion.
* **Per-seed regression floors** — EVERY seed must individually clear the
  per-class and key-SNR regression caps (``maximum_*_drop``), so no seed is
  allowed to regress a class or SNR band even if the mean looks healthy.

Final PASS = both halves hold.  Thresholds are read verbatim from
``promotion_gates`` and are never lowered here.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path

import pandas as pd
import yaml

from training.qam_aware_v3_2_utils import write_text_lf
from training.utils import resolve_project_path

SEED_NAME = re.compile(r"seed(\d+)$")


def _seed_label(seed_dir: Path) -> str:
    match = SEED_NAME.search(seed_dir.name)
    return match.group(1) if match else seed_dir.name


def load_seed_record(seed_dir: Path, v2: dict) -> dict:
    report = json.loads((seed_dir / "tables" / "evaluation.json").read_text(encoding="utf-8"))
    suite = report["suites"]["v2_compatible"]
    snr = pd.read_csv(seed_dir / "tables" / "v2_compatible_snr_metrics.csv")
    snr_accuracy = {str(int(row.snr_db)): float(row.accuracy) for row in snr.itertuples()}
    return {
        "seed": _seed_label(seed_dir),
        "checkpoint": str(report.get("checkpoint")),
        "accuracy": float(suite["accuracy"]),
        "macro_f1": float(suite["macro_f1"]),
        "qam_mean_accuracy": float(suite["qam_mean_accuracy"]),
        "per_class_accuracy": {name: float(value) for name, value in suite["per_class_accuracy"].items()},
        "snr_accuracy": {key: snr_accuracy[key] for key in v2["snr_accuracy"]},
    }


def summarize(records: list[dict]) -> dict:
    scalar_keys = ("accuracy", "macro_f1", "qam_mean_accuracy")
    mean = {key: statistics.fmean(float(record[key]) for record in records) for key in scalar_keys}
    std = {
        key: statistics.pstdev(float(record[key]) for record in records)
        if len(records) > 1
        else 0.0
        for key in scalar_keys
    }

    classes = list(records[0]["per_class_accuracy"].keys())
    per_class = {}
    for name in classes:
        values = [float(record["per_class_accuracy"][name]) for record in records]
        per_class[name] = {
            "mean": statistics.fmean(values),
            "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
        }

    snr_keys = list(records[0]["snr_accuracy"].keys())
    snr = {}
    for key in snr_keys:
        values = [float(record["snr_accuracy"][key]) for record in records]
        snr[key] = {
            "mean": statistics.fmean(values),
            "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
        }

    return {"mean": mean, "std": std, "per_class": per_class, "snr": snr}


def apply_multi_seed_rule(records: list[dict], v2: dict, gates: dict) -> dict:
    if not records:
        raise RuntimeError("No seed records to gate; the three-seed run produced nothing.")

    summary = summarize(records)
    mean = summary["mean"]
    checks: dict[str, bool] = {}
    values: dict[str, float] = {}

    accuracy_gain = mean["accuracy"] - float(v2["accuracy"])
    f1_gain = mean["macro_f1"] - float(v2["macro_f1"])
    qam_gain = mean["qam_mean_accuracy"] - float(v2["qam_mean_accuracy"])
    values["mean_accuracy_gain"] = accuracy_gain
    values["mean_macro_f1_gain"] = f1_gain
    values["mean_qam_mean_gain"] = qam_gain
    checks["mean_accuracy_gain"] = accuracy_gain >= float(gates["minimum_accuracy_gain"])
    checks["mean_macro_f1_gain"] = f1_gain >= float(gates["minimum_macro_f1_gain"])
    checks["mean_qam_mean_gain"] = qam_gain >= float(gates["minimum_qam_mean_gain"])

    max_class_drop = float(gates["maximum_per_class_accuracy_drop"])
    max_snr_drop = float(gates["maximum_key_snr_accuracy_drop"])
    for record in records:
        seed = record["seed"]
        for name, baseline in v2["per_class_accuracy"].items():
            drop = float(baseline) - float(record["per_class_accuracy"][name])
            values[f"seed{seed}_per_class_delta_{name}"] = -drop
            checks[f"seed{seed}_per_class_{name}"] = drop <= max_class_drop
        for key, baseline in v2["snr_accuracy"].items():
            drop = float(baseline) - float(record["snr_accuracy"][key])
            values[f"seed{seed}_snr_delta_{key}"] = -drop
            checks[f"seed{seed}_snr_{key}"] = drop <= max_snr_drop

    return {
        "rule": "mean_improvement_and_per_seed_regression_floors",
        "improvement_on": "mean",
        "regression_floors_on": "every_seed",
        "checks": checks,
        "values": values,
        "passed": all(checks.values()),
    }


def check_multi_seed_acceptance(seed_dirs: list[Path], gate_path: str = "configs/qam_aware_v3_2_acceptance.yaml") -> dict:
    gate_config = yaml.safe_load(resolve_project_path(gate_path).read_text(encoding="utf-8"))
    v2 = gate_config["v2"]
    gates = gate_config["promotion_gates"]

    records = [load_seed_record(Path(seed_dir), v2) for seed_dir in seed_dirs]
    summary = summarize(records)
    rule = apply_multi_seed_rule(records, v2, gates)

    result = {
        "reference": gate_config["reference"],
        "scope": "V2 exact development namespace; final blind set not accessed",
        "seeds": [record["seed"] for record in records],
        "per_seed": records,
        "mean": summary["mean"],
        "std": summary["std"],
        "per_class_summary": summary["per_class"],
        "snr_summary": summary["snr"],
        "rule": rule["rule"],
        "improvement_on": rule["improvement_on"],
        "regression_floors_on": rule["regression_floors_on"],
        "checks": rule["checks"],
        "values": rule["values"],
        "passed": rule["passed"],
    }
    return result


def run_multi_seed_acceptance(
    seed_dirs: list[Path],
    gate_path: str = "configs/qam_aware_v3_2_acceptance.yaml",
    out: str = "outputs/qam_aware_v3_2/formal/aggregate/v3_2_acceptance.json",
) -> dict:
    """Evaluate the gate and write the acceptance, per-seed and mean/std reports."""

    result = check_multi_seed_acceptance(seed_dirs, gate_path)
    destination = resolve_project_path(out)
    write_text_lf(destination, json.dumps(result, indent=2) + "\n")
    write_text_lf(
        destination.parent / "per_seed_summary.json",
        json.dumps(result["per_seed"], indent=2) + "\n",
    )
    aggregate = {
        "mean": result["mean"],
        "std": result["std"],
        "per_class": result["per_class_summary"],
        "snr": result["snr_summary"],
        "seeds": result["seeds"],
    }
    write_text_lf(destination.parent / "aggregate_summary.json", json.dumps(aggregate, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed-dirs",
        nargs="+",
        required=True,
        help="Per-seed output directories (each contains tables/evaluation.json).",
    )
    parser.add_argument(
        "--gates",
        default="configs/qam_aware_v3_2_acceptance.yaml",
    )
    parser.add_argument(
        "--out",
        default="outputs/qam_aware_v3_2/formal/aggregate/v3_2_acceptance.json",
    )
    args = parser.parse_args()

    result = run_multi_seed_acceptance([Path(path) for path in args.seed_dirs], args.gates, args.out)

    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
