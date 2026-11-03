"""Fail closed unless V3.2 materially improves the frozen V2 development baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from training.utils import resolve_project_path


def check_acceptance(
    report_path: str,
    snr_path: str,
    gate_path: str = "configs/qam_aware_v3_2_acceptance.yaml",
) -> dict[str, object]:
    report = json.loads(resolve_project_path(report_path).read_text(encoding="utf-8"))
    gates = yaml.safe_load(resolve_project_path(gate_path).read_text(encoding="utf-8"))
    suite = report["suites"]["v2_compatible"]
    v2 = gates["v2"]
    policy = gates["promotion_gates"]
    checks: dict[str, bool] = {}
    values: dict[str, float | None] = {}

    accuracy_gain = float(suite["accuracy"]) - float(v2["accuracy"])
    f1_gain = float(suite["macro_f1"]) - float(v2["macro_f1"])
    qam_gain = float(suite["qam_mean_accuracy"]) - float(v2["qam_mean_accuracy"])
    values.update(accuracy_gain=accuracy_gain, macro_f1_gain=f1_gain, qam_mean_gain=qam_gain)
    checks["accuracy_gain"] = accuracy_gain >= float(policy["minimum_accuracy_gain"])
    checks["macro_f1_gain"] = f1_gain >= float(policy["minimum_macro_f1_gain"])
    checks["qam_mean_gain"] = qam_gain >= float(policy["minimum_qam_mean_gain"])

    allowed_drop = float(policy["maximum_per_class_accuracy_drop"])
    for name, baseline in v2["per_class_accuracy"].items():
        current = float(suite["per_class_accuracy"][name])
        values[f"per_class_delta_{name}"] = current - float(baseline)
        checks[f"per_class_{name}"] = current >= float(baseline) - allowed_drop

    snr = pd.read_csv(resolve_project_path(snr_path))
    allowed_snr_drop = float(policy["maximum_key_snr_accuracy_drop"])
    for key, baseline in v2["snr_accuracy"].items():
        rows = snr[snr["snr_db"] == float(key)]
        if len(rows) != 1:
            checks[f"snr_{key}"] = False
            values[f"snr_delta_{key}"] = None
            continue
        current = float(rows.iloc[0]["accuracy"])
        values[f"snr_delta_{key}"] = current - float(baseline)
        checks[f"snr_{key}"] = current >= float(baseline) - allowed_snr_drop

    passed = all(checks.values())
    result: dict[str, object] = {
        "reference": gates["reference"],
        "scope": "V2 exact development namespace; final blind set not accessed",
        "checks": checks,
        "values": values,
        "passed": passed,
    }
    destination = resolve_project_path(report_path).with_name("v3_2_acceptance.json")
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="outputs/qam_aware_v3_2/formal/tables/evaluation.json")
    parser.add_argument("--snr", default="outputs/qam_aware_v3_2/formal/tables/v2_compatible_snr_metrics.csv")
    parser.add_argument("--gates", default="configs/qam_aware_v3_2_acceptance.yaml")
    args = parser.parse_args()
    result = check_acceptance(args.report, args.snr, args.gates)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
