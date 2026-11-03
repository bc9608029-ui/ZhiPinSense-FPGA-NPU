"""Semantic OOD baselines for the trained models (M11/M12).

Computes the full ranking + working-point report (MSP / Entropy / MaxLogit /
Energy) for the 24-class benchmark, and (once the 12-class V2 checkpoint is
imported) for the 12-class model.  The 12-class axis fails closed while its
checkpoint is still PENDING.  Writes a compact JSON report (per-sample
score/decision vectors are dropped; the ranking CIs and working points are kept).
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from evaluation.evaluate_ood import evaluate_ood_12class, evaluate_ood_rml24
from training.utils import load_yaml, save_json

_DROP_KEYS = {"id_labels", "ood_scores", "decisions"}


def _compact(node: Any) -> Any:
    if isinstance(node, dict):
        return {key: _compact(value) for key, value in node.items() if key not in _DROP_KEYS}
    if isinstance(node, list):
        return [_compact(item) for item in node]
    return node


def run_ood_baselines(config_path: str, checkpoint_path: str, *, output_path: str | None = None,
                      samples: int | None = None, count_per_modulation: int = 256,
                      include_12class: bool = False) -> dict[str, Any]:
    config = load_yaml(config_path)
    report: dict[str, Any] = {}
    report["rml24"] = evaluate_ood_rml24(
        config, checkpoint_path, samples=samples, count_per_modulation=count_per_modulation,
    )
    # MSP/Entropy/MaxLogit/Energy are post-hoc scoring methods over the frozen
    # checkpoint; the OOD baseline never trains a model (budget = 0 runs).
    report["model_training_runs"] = 0
    if include_12class:
        try:
            report["12class"] = evaluate_ood_12class(config, checkpoint_path)
        except (RuntimeError, NotImplementedError) as exc:
            report["12class"] = {"blocked": str(exc)}
    destination = output_path or "runs/ood_baselines/ood_baselines.json"
    save_json(_compact(report), destination)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/rml24_base.yaml")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--samples", type=int, default=None)
    parser.add_argument("--count-per-modulation", type=int, default=256)
    parser.add_argument("--include-12class", action="store_true")
    args = parser.parse_args()
    report = run_ood_baselines(args.config, args.checkpoint, output_path=args.output,
                               samples=args.samples,
                               count_per_modulation=args.count_per_modulation,
                               include_12class=args.include_12class)
    print("OOD_BASELINE model_training_runs=0", flush=True)
    print(json.dumps(_compact(report), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
