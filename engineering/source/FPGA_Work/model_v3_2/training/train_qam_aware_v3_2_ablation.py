"""Run the V3.2 controlled ablations (A0-A3) on train/validation only.

Each candidate shares the same V2-initialized backbone + zero-gated QAM delta
branch and the same fixed split/seed; they differ only in the loss.  A0 is the
frozen V2 reference recorded in ``configs/qam_aware_v3_2_acceptance.yaml`` (no
training run).  A1-A3 are trained for ``ablation_epochs`` and ranked by
validation macro-F1 / accuracy.  The final blind set is never instantiated.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd
import yaml

from training.train_qam_aware_v3_2 import train_v3_2
from training.qam_aware_v3_2_utils import write_text_lf
from training.utils import resolve_project_path


def _read_ablation(path: str) -> dict:
    raw = yaml.safe_load(resolve_project_path(path).read_text(encoding="utf-8"))
    return raw


def _write_override(config: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def run_ablations(ablation_path: str = "configs/qam_aware_v3_2_ablation.yaml") -> dict:
    spec = _read_ablation(ablation_path)
    base_experiment = spec["experiment_config"]
    root = Path(spec["output_root"])
    epochs = int(spec["ablation_epochs"])

    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    rows: list[dict] = []
    # A0: frozen V2 reference (no training).
    rows.append(
        {
            "variant": "a0_frozen_v2_reference",
            "distill": "n/a",
            "qam_weight": "n/a",
            "trained": False,
            "val_accuracy": None,
            "val_macro_f1": None,
            "best_epoch": None,
            "note": "frozen V2 champion (see acceptance.yaml)",
        }
    )

    for name, variant in spec["variants"].items():
        override = {
            "experiment_config": base_experiment,
            "output_root": str(root / name),
            "training": {
                "epochs": epochs,
                "minimum_epochs_before_stopping": min(epochs, 10),
                "distillation": variant["distillation"],
                "class_weights": variant["class_weights"],
            },
        }
        config_file = root / f"{name}_config.yaml"
        _write_override(override, config_file)
        train_v3_2(str(config_file), stop_after_epoch=epochs)

        manifest_path = root / name / "logs" / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        best = manifest["best_metrics"]
        rows.append(
            {
                "variant": name,
                "distill": bool(variant["distillation"].get("enabled", False)),
                "qam_weight": variant["class_weights"].get("16QAM", 1.0),
                "trained": True,
                "val_accuracy": float(best.get("val_accuracy")),
                "val_macro_f1": float(best.get("val_macro_f1")),
                "best_epoch": int(manifest["best_epoch"]),
                "note": variant.get("description", ""),
                # Full training override, frozen verbatim so the selection step
                # can reconstruct the winning candidate without re-reading the
                # ablation spec.
                "training": {
                    "distillation": dict(variant["distillation"]),
                    "class_weights": dict(variant["class_weights"]),
                },
            }
        )

    csv_frame = pd.DataFrame([{key: value for key, value in row.items() if key != "training"} for row in rows])
    csv_frame.to_csv(root / "ablation_comparison.csv", index=False)
    summary = {
        "experiment": base_experiment,
        "ablation_epochs": epochs,
        "scope": "train/validation only; v3_2_final_blind_test was not accessed",
        "final_blind_test_accessed": False,
        "variants": rows,
    }
    write_text_lf(root / "ablation_summary.json", json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v3_2_ablation.yaml")
    args = parser.parse_args()
    print(json.dumps(run_ablations(args.config), indent=2))


if __name__ == "__main__":
    main()
