"""Evaluate the two completed AD-AMR P0 runs against frozen V2.

This is evaluation-only.  It uses validation namespaces exclusively, evaluates
candidate and V2 on identical records, runs the fixed OOD battery, checks ONNX
Runtime parity, and applies the existing pilot gate thresholds.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from evaluation.evaluate_ad_amr_pilot import evaluate_paired, ood_channel_configs
from scripts.export_ad_amr_onnx import export_ad_amr
from scripts.run_pilot import decide_gates
from training.utils import load_yaml, save_json


ROOT = Path("outputs/ad_amr_v1/final")
SEEDS = (2026, 2027)


def config_for(base: dict[str, Any], seed: int) -> dict[str, Any]:
    cfg = copy.deepcopy(base)
    cfg["device"] = "cuda:0"
    cfg["seed"] = seed
    cfg["training"]["loss"]["variant"] = "P0"
    cfg["output_root"] = str(ROOT / f"s{seed}")
    return cfg


def main() -> int:
    base = load_yaml("configs/ad_amr_v1.yaml")
    pilot = base["pilot"]
    records: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}

    for seed in SEEDS:
        cfg = config_for(base, seed)
        checkpoint = ROOT / f"s{seed}/checkpoints/best.pt"
        summary_path = ROOT / f"s{seed}/checkpoints/training_summary.json"
        if not checkpoint.is_file() or not summary_path.is_file():
            raise FileNotFoundError(f"missing completed seed {seed}: {checkpoint}")

        summaries[str(seed)] = json.loads(summary_path.read_text(encoding="utf-8"))
        paired = evaluate_paired(cfg, checkpoint, split="ad_amr_validation")
        ood: dict[str, Any] = {}
        for domain, channel_cfg in ood_channel_configs(cfg["channel"]).items():
            ood[domain] = evaluate_paired(
                cfg,
                checkpoint,
                split=f"ad_amr_validation_ood_{domain}",
                channel_config=channel_cfg,
                samples=int(pilot["ood_samples"]),
            )
        records.append(
            {
                "seed": seed,
                "checkpoint": str(checkpoint),
                "paired": paired,
                "ood": ood,
            }
        )

    export_cfg = config_for(base, SEEDS[0])
    onnx_report = export_ad_amr(export_cfg, records[0]["checkpoint"])
    onnx_ok = onnx_report["ort_parity"]["status"] == "ok"
    thresholds = {name: float(value) for name, value in pilot["gates"].items()}
    gates = decide_gates(records, thresholds, training_complete=True, onnx_ok=onnx_ok)
    passed = all(gate["pass"] for gate in gates)

    report = {
        "candidate": "AD-AMR V1 P0, independent 100-epoch-cap runs",
        "training_summaries": summaries,
        "paired_seed_results": records,
        "thresholds": thresholds,
        "gates": gates,
        "onnx": onnx_report,
        "promoted": passed,
        "selection_scope": "validation only; test/final blind never instantiated",
        "marker": "AD_AMR_V1_FINAL_PASS" if passed else "AD_AMR_V1_FINAL_NO_GO",
    }
    destination = ROOT / "final_acceptance.json"
    save_json(report, destination)
    print(json.dumps({"promoted": passed, "gates": gates}, indent=2))
    print(report["marker"])
    print(f"report={destination}")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
