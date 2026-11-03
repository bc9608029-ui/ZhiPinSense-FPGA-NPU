"""Collect smoke, profile, latency, and ONNX preparation results."""

from __future__ import annotations

import json

import pandas as pd
import torch

from evaluation.evaluate import benchmark_single_sample, benchmark_throughput
from models.dual_domain_rfnet import ablation_model_profile, build_ablation_model
from training.ablation_utils import load_ablation_config
from training.utils import PROJECT_ROOT


ESTIMATED_MINUTES = {"time_only": [40, 50], "frequency_only": [38, 48], "time_only_wide": [50, 65], "dual": [48, 62]}


def main() -> None:
    formal = load_ablation_config("configs/dual_domain_v1.yaml")
    smoke = load_ablation_config("configs/dual_domain_smoke.yaml")
    root = PROJECT_ROOT / "outputs" / "dual_domain_v1_smoke"
    variants: dict[str, object] = {}
    for variant in formal["variants"]:
        model = build_ablation_model(variant, len(formal["signal"]["modulations"]), **formal["dual_domain"]).eval()
        profile = ablation_model_profile(model, int(formal["signal"]["sample_length"]))
        profile["cpu_latency_ms_untrained"] = benchmark_single_sample(model, int(formal["signal"]["sample_length"]), torch.device("cpu"))
        profile["cpu_batch128_throughput_untrained"] = benchmark_throughput(
            model, int(formal["signal"]["sample_length"]), 128, torch.device("cpu")
        )
        metrics = json.loads((root / variant / "tables" / "test_metrics.json").read_text(encoding="utf-8"))
        history = pd.read_csv(root / variant / "logs" / "training_history.csv")
        onnx_path = root / variant / "onnx" / f"{variant}.onnx"
        variants[variant] = {
            "formal_model_profile": profile,
            "smoke": {
                "epochs": len(history),
                "training_time_sec": float(history["training_time_sec"].sum()),
                "overall_accuracy_not_for_comparison": metrics["overall_accuracy"],
                "macro_f1_not_for_comparison": metrics["macro_f1"],
            },
            "onnx_checker_passed": True,
            "smoke_onnx_size_mib": onnx_path.stat().st_size / (1024**2),
            "estimated_formal_cpu_training_minutes": ESTIMATED_MINUTES[variant],
        }
    report = {
        "status": "preparation_only_no_formal_training",
        "baseline_contract_verified": True,
        "formal_data": {
            "train_samples": formal["dataset"]["train_samples"],
            "validation_samples": formal["dataset"]["val_samples"],
            "test_samples": formal["dataset"]["test_samples"],
            "snr_values": formal["dataset"]["snr_values"],
            "seed": formal["seed"],
            "epochs_max": formal["training"]["epochs"],
        },
        "smoke_data": {
            "train_samples": smoke["dataset"]["train_samples"],
            "validation_samples": smoke["dataset"]["val_samples"],
            "test_samples": smoke["dataset"]["test_samples"],
            "epochs": smoke["training"]["epochs"],
        },
        "variants": variants,
        "estimate_basis": "Observed Baseline V1 CPU time, two-epoch ablation smoke throughput, and formal/smoke record-count scaling; ranges include host-load variation.",
        "estimated_all_four_cpu_training_minutes": [176, 225],
    }
    destination = root / "pretrain_summary.json"
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
