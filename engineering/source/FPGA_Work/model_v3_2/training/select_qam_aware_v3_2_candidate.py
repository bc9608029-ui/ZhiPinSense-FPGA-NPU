"""Freeze the winning ablation candidate using a pre-written, validation-only rule.

The rule is deliberately fixed (not learned, not tuned against any test set):

    1. Consider only trained candidates (A1-A3; A0 is the frozen V2 reference
       and is never a trainable option).
    2. Reject any candidate whose validation metrics are missing or non-finite.
    3. Rank by ``val_macro_f1`` descending, then ``val_accuracy`` descending,
       then variant name ascending (deterministic tie-break).
    4. The winner is the single top-ranked candidate.

The winning candidate's full ``training`` override (``distillation`` +
``class_weights``) is frozen into ``selected_candidate.yaml``/``.json``.  The
three-seed formal run then reads this frozen file and never re-selects, so an
interrupted/resumed job cannot silently change which candidate it is training.

No test / v2_compatible / final_blind_test metric participates in selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import yaml

from training.qam_aware_v3_2_utils import write_text_lf
from training.utils import resolve_project_path

SELECTION_RULE = "validation_only_macro_f1_then_accuracy"
SELECTION_SCOPE = "train/validation only; v3_2_final_blind_test was not accessed"


def select_candidate(summary: dict) -> dict:
    variants = list(summary.get("variants", []))
    trained = [variant for variant in variants if variant.get("trained") is True]
    if not trained:
        raise RuntimeError("No trained ablation candidates to select from (A1-A3 all missing).")

    for variant in trained:
        accuracy = float(variant.get("val_accuracy"))
        macro_f1 = float(variant.get("val_macro_f1"))
        if not (math.isfinite(accuracy) and math.isfinite(macro_f1)):
            raise RuntimeError(f"Ablation candidate {variant['variant']!r} has non-finite validation metrics.")
        training = variant.get("training")
        if not isinstance(training, dict) or "distillation" not in training or "class_weights" not in training:
            raise RuntimeError(
                f"Ablation candidate {variant['variant']!r} is missing its full training override; "
                "cannot freeze the selected config."
            )

    ranked = sorted(
        trained,
        key=lambda variant: (
            -float(variant["val_macro_f1"]),
            -float(variant["val_accuracy"]),
            str(variant["variant"]),
        ),
    )
    winner = ranked[0]
    return {
        "selected_variant": str(winner["variant"]),
        "selection_rule": SELECTION_RULE,
        "selection_scope": SELECTION_SCOPE,
        "selection_metric": {
            "val_macro_f1": float(winner["val_macro_f1"]),
            "val_accuracy": float(winner["val_accuracy"]),
        },
        "best_epoch": int(winner["best_epoch"]),
        "training": {
            "distillation": dict(winner["training"]["distillation"]),
            "class_weights": dict(winner["training"]["class_weights"]),
        },
    }


def freeze_candidate(summary_path: str, out_path: str) -> dict:
    summary_file = resolve_project_path(summary_path)
    summary = json.loads(summary_file.read_text(encoding="utf-8"))
    candidate = select_candidate(summary)
    candidate["frozen_at_ablation_summary_sha256"] = hashlib.sha256(summary_file.read_bytes()).hexdigest()

    destination = resolve_project_path(out_path)
    yaml_text = yaml.safe_dump(candidate, sort_keys=False)
    write_text_lf(destination, yaml_text)
    json_text = json.dumps(candidate, indent=2) + "\n"
    write_text_lf(destination.with_suffix(".json"), json_text)
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--summary",
        default="outputs/qam_aware_v3_2/ablation/ablation_summary.json",
    )
    parser.add_argument(
        "--out",
        default="outputs/qam_aware_v3_2/formal/selected_candidate.yaml",
    )
    args = parser.parse_args()
    candidate = freeze_candidate(args.summary, args.out)
    print(json.dumps(candidate, indent=2))


if __name__ == "__main__":
    main()
