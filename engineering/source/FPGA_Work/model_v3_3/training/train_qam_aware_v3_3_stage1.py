"""Run the V3.3 Stage-1 controlled ablations (A0-A3) on two selection seeds.

Each trainable candidate (A1-A3) shares the same frozen-V2 backbone and differs
only in which train-only heads/losses are enabled.  A0 is not a training run: the
*frozen V2 checkpoint is loaded and re-inferred* on the same two validation seeds
(FP32 + FPGA-sim) as the trained candidates — it is never a metric copied from
the acceptance YAML.

Candidate ranking is performed strictly on the **validation** namespace
(``v3_3_validation`` with the selection seed as data seed) plus the synthetic OOD
domains (also seeded by the selection seed).  The development test and final
blind namespaces are never instantiated; a split-access guard raises immediately
if they are, and the full access audit is saved so the isolation is provable.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd
import yaml

from evaluation.evaluate_qam_aware_v3_3 import evaluate_v3_3_a0_validation, evaluate_v3_3_validation
from evaluation.evaluate_qam_aware_v3_3_ood import evaluate_v3_3_a0_ood, evaluate_v3_3_ood
from training.qam_aware_v3_3_utils import write_text_lf
from training.train_qam_aware_v3_3 import train_v3_3
from training.utils import PROJECT_ROOT, resolve_project_path
from training.v3_3_split_guard import (
    FORBIDDEN_SPLITS,
    enter_selection_scope,
    exit_selection_scope,
)


def _read_yaml(path: str) -> dict:
    data = yaml.safe_load(resolve_project_path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a mapping: {path}")
    return data


def _write_override(config: dict, path: Path) -> None:
    write_text_lf(path, yaml.safe_dump(config, sort_keys=False))


def _seed_metrics_from_validation(report: dict) -> dict:
    summary = report["validation"]
    gap = report["fpga_sim_gap"]
    return {
        "accuracy": float(summary["accuracy"]),
        "macro_f1": float(summary["macro_f1"]),
        "qam_mean_accuracy": float(summary["qam_mean_accuracy"]),
        "per_class_accuracy": {name: float(value) for name, value in summary["per_class_accuracy"].items()},
        "fpga_sim_accuracy_gap": float(gap.get("accuracy_gap", 0.0)),
        "fpga_sim_macro_f1_gap": float(gap.get("macro_f1_gap", 0.0)),
    }


def _seed_ood(report: dict) -> dict:
    return {
        "worst_domain_macro_f1": float(report["worst_domain_macro_f1"]),
        "domains": report["domains"],
    }


def _evaluate_trained_seed(config_path: str, seed: int) -> dict:
    record = _seed_metrics_from_validation(evaluate_v3_3_validation(config_path, seed=seed))
    record["ood"] = _seed_ood(evaluate_v3_3_ood(config_path, seed=seed))
    return record


def _evaluate_a0_seed(base_experiment_path: str, seed: int) -> dict:
    record = _seed_metrics_from_validation(
        evaluate_v3_3_a0_validation(base_experiment_path, seed=seed)
    )
    record["ood"] = _seed_ood(evaluate_v3_3_a0_ood(base_experiment_path, seed=seed))
    return record


def run_stage1(ablation_path: str = "configs/qam_aware_v3_3_stage1.yaml") -> dict:
    spec = _read_yaml(ablation_path)
    base_experiment = spec["experiment_config"]
    root = resolve_project_path(spec["output_root"])
    epochs = int(spec["ablation_epochs"])
    seeds = [int(seed) for seed in spec["selection_seeds"]]
    ood_samples = spec.get("ood", {}).get("samples")
    ood_enabled = bool(spec.get("ood", {}).get("enabled", True))

    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    variants = spec["variants"]
    rows: list[dict] = []

    # Arm the split-access guard for the whole selection run.
    enter_selection_scope()
    try:
        for name, variant in variants.items():
            trained = bool(variant.get("trained", True))
            seed_records: dict[str, dict] = {}
            for seed in seeds:
                if not trained:
                    seed_records[str(seed)] = _evaluate_a0_seed(base_experiment, seed)
                    continue

                seed_dir = root / name / f"seed{seed}"
                override = {
                    "experiment_config": base_experiment,
                    "seed": seed,
                    "output_root": seed_dir.relative_to(PROJECT_ROOT).as_posix(),
                    "model": dict(variant["model"]),
                    "training": dict(variant["training"]),
                }
                config_file = root / name / f"seed{seed}_config.yaml"
                _write_override(override, config_file)
                train_v3_3(str(config_file), stop_after_epoch=epochs)
                seed_records[str(seed)] = _evaluate_trained_seed(str(config_file), seed)

            rows.append(
                {
                    "variant": name,
                    "trained": trained,
                    "description": variant.get("description", ""),
                    "seeds": seed_records,
                    "model": dict(variant["model"]),
                    "training": dict(variant["training"]),
                }
            )
    finally:
        accessed = exit_selection_scope()

    forbidden_accessed = [split for split in accessed if split in FORBIDDEN_SPLITS]
    access_audit = {
        "scope": "stage1_candidate_selection",
        "selection_seeds": seeds,
        "accessed_splits": sorted(set(accessed)),
        "forbidden_splits_accessed": forbidden_accessed,
        "test_accessed": "test" in accessed,
        "final_blind_test_accessed": "v3_3_final_blind_test" in accessed,
    }
    write_text_lf(root / "access_audit.json", json.dumps(access_audit, indent=2) + "\n")
    if forbidden_accessed:
        raise RuntimeError(
            f"Stage-1 selection accessed forbidden splits {forbidden_accessed}; "
            "candidate ranking must use the validation namespace only."
        )

    comparison = []
    for row in rows:
        comparison.append(
            {
                "variant": row["variant"],
                "trained": row["trained"],
                "n_seeds": len(row["seeds"]),
                "mean_accuracy": round(sum(float(s["accuracy"]) for s in row["seeds"].values()) / len(row["seeds"]), 6),
                "mean_macro_f1": round(sum(float(s["macro_f1"]) for s in row["seeds"].values()) / len(row["seeds"]), 6),
                "mean_qam_mean_accuracy": round(
                    sum(float(s["qam_mean_accuracy"]) for s in row["seeds"].values()) / len(row["seeds"]), 6
                ),
                "description": row["description"],
            }
        )
    pd.DataFrame(comparison).to_csv(root / "ablation_comparison.csv", index=False)

    summary = {
        "experiment": base_experiment,
        "ablation_epochs": epochs,
        "selection_seeds": seeds,
        "ood_enabled": ood_enabled,
        "ood_samples": ood_samples,
        "scope": "validation namespace only; test and v3_3_final_blind_test were not accessed",
        "final_blind_test_accessed": access_audit["final_blind_test_accessed"],
        "test_accessed": access_audit["test_accessed"],
        "access_audit": access_audit,
        "variants": rows,
    }
    write_text_lf(root / "ablation_summary.json", json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_3_stage1.yaml")
    args = parser.parse_args()
    print(json.dumps(run_stage1(args.config), indent=2))


if __name__ == "__main__":
    main()
