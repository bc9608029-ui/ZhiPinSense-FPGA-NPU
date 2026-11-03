"""Create the unified four-way DualDomain V1 ablation report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binomtest

from training.ablation_utils import load_ablation_config
from training.utils import resolve_project_path


KEY_SNRS = (-12, -10, -8, -6, -4, 0, 10, 20)


def _mcnemar(root: Path, first: str, second: str) -> dict[str, float | int | bool]:
    a = pd.read_csv(root / first / "tables" / "test_predictions.csv")
    b = pd.read_csv(root / second / "tables" / "test_predictions.csv")
    if not np.array_equal(a["target"], b["target"]):
        raise RuntimeError("Evaluation targets differ across variants; fairness comparison aborted.")
    a_correct = a["target"].to_numpy() == a["prediction"].to_numpy()
    b_correct = b["target"].to_numpy() == b["prediction"].to_numpy()
    first_only = int(np.sum(a_correct & ~b_correct))
    second_only = int(np.sum(~a_correct & b_correct))
    discordant = first_only + second_only
    p_value = float(binomtest(min(first_only, second_only), discordant, 0.5).pvalue) if discordant else 1.0
    return {
        f"{first}_only_correct": first_only,
        f"{second}_only_correct": second_only,
        "discordant_samples": discordant,
        "exact_two_sided_p_value": p_value,
        f"{second}_significantly_better": bool(second_only > first_only and p_value < 0.05),
    }


def compare(config_path: str) -> dict[str, object]:
    config = load_ablation_config(config_path)
    root = resolve_project_path(config["output_root"])
    comparison = root / "comparison"
    figures, tables, config_dir = comparison / "figures", comparison / "tables", comparison / "config"
    figures.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    overall_rows, snr_frames, per_class_rows, per_modulation_frames = [], [], [], []
    for variant in config["variants"]:
        metrics = json.loads((root / variant / "tables" / "test_metrics.json").read_text(encoding="utf-8"))
        profile = json.loads((root / variant / "tables" / "model_profile.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / variant / "logs" / "run_manifest.json").read_text(encoding="utf-8"))
        history = pd.read_csv(root / variant / "logs" / "training_history.csv")
        best_history = history.loc[history["epoch"] == metrics["best_epoch"]].iloc[0]
        last_history = history.iloc[-1]
        per_class = metrics["per_class_accuracy"]
        overall_rows.append({
            "variant": variant,
            "overall_accuracy": metrics["overall_accuracy"],
            "macro_f1": metrics["macro_f1"],
            "qpsk_accuracy": per_class["QPSK"],
            "8psk_accuracy": per_class["8PSK"],
            "16qam_accuracy": per_class["16QAM"],
            "64qam_accuracy": per_class["64QAM"],
            "trainable_parameters": profile["trainable_parameters"],
            "fixed_non_trainable_state_mb": profile["fixed_non_trainable_state_mb"],
            "neural_macs": profile["neural_macs"],
            "neural_flops": profile["neural_flops"],
            "frontend_macs_pc_reference": profile["frontend_macs_pc_reference"],
            "frontend_flops_pc_reference": profile["frontend_flops_pc_reference"],
            "total_software_macs": profile["total_software_macs"],
            "total_software_flops": profile["total_software_flops"],
            "checkpoint_tensor_state_size_mb": profile["checkpoint_tensor_state_size_mb"],
            "projected_npu_model_size_mb": profile["projected_npu_model_size_mb"],
            "single_sample_cpu_ms": metrics["single_sample_cpu_ms"],
            "training_time_sec": manifest["training_time_sec"],
            "peak_process_rss_mb": manifest["peak_process_rss_mb"],
            "best_epoch": metrics["best_epoch"],
            "epochs_completed": int(last_history["epoch"]),
            "best_val_loss": float(best_history["val_loss"]),
            "best_train_val_accuracy_gap": float(best_history["train_accuracy"] - best_history["val_accuracy"]),
            "last_train_val_accuracy_gap": float(last_history["train_accuracy"] - last_history["val_accuracy"]),
        })
        per_class_rows.extend({"variant": variant, "modulation": key, "accuracy": value} for key, value in per_class.items())
        frame = pd.read_csv(root / variant / "tables" / "snr_metrics.csv")
        frame["variant"] = variant
        snr_frames.append(frame)
        per_modulation = pd.read_csv(root / variant / "tables" / "snr_per_modulation_accuracy.csv")
        per_modulation["variant"] = variant
        per_modulation_frames.append(per_modulation)
    overall = pd.DataFrame(overall_rows)
    snr = pd.concat(snr_frames, ignore_index=True)
    per_class_frame = pd.DataFrame(per_class_rows)
    per_modulation = pd.concat(per_modulation_frames, ignore_index=True)
    overall.to_csv(tables / "overall_comparison.csv", index=False)
    snr.to_csv(tables / "snr_comparison.csv", index=False)
    snr[snr["snr_db"].isin(KEY_SNRS)].to_csv(tables / "key_snr_comparison.csv", index=False)
    per_class_frame.to_csv(tables / "per_class_comparison.csv", index=False)
    per_modulation.to_csv(tables / "snr_per_modulation_comparison.csv", index=False)
    per_modulation[per_modulation["snr_db"].isin(KEY_SNRS)].to_csv(
        tables / "key_snr_per_modulation_comparison.csv", index=False
    )
    snapshot = {key: value for key, value in config.items() if not key.startswith("_")}
    (config_dir / "effective_config.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    for metric, filename in (("accuracy", "snr_accuracy_comparison.png"), ("macro_f1", "snr_f1_comparison.png")):
        fig, axis = plt.subplots(figsize=(9, 5.5))
        for variant in config["variants"]:
            subset = snr[snr["variant"] == variant]
            axis.plot(subset["snr_db"], subset[metric], marker="o", label=variant)
        axis.set(title=f"Four-way ablation {metric} versus SNR", xlabel="SNR (dB)", ylabel=metric, ylim=(0, 1.02))
        axis.grid(True, alpha=0.3)
        axis.legend()
        fig.tight_layout()
        fig.savefig(figures / filename, dpi=180)
        plt.close(fig)

    modulations = list(config["signal"]["modulations"])
    fig, axes = plt.subplots(2, 4, figsize=(16, 8), sharex=True, sharey=True)
    for axis, modulation in zip(axes.flat, modulations):
        for variant in config["variants"]:
            subset = per_modulation[
                (per_modulation["variant"] == variant) & (per_modulation["modulation"] == modulation)
            ]
            axis.plot(subset["snr_db"], subset["accuracy"], marker="o", markersize=3, label=variant)
        axis.set_title(modulation)
        axis.set_xlabel("SNR (dB)")
        axis.set_ylabel("Accuracy")
        axis.set_ylim(0, 1.02)
        axis.grid(True, alpha=0.3)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("Per-modulation Accuracy versus SNR")
    fig.tight_layout()
    fig.savefig(figures / "snr_per_modulation_comparison.png", dpi=180)
    plt.close(fig)

    indexed = overall.set_index("variant")
    low = snr[snr["snr_db"].isin((-12, -10, -8, -6))].groupby("variant")["accuracy"].mean()
    qam = indexed[["16qam_accuracy", "64qam_accuracy"]].mean(axis=1)
    significance = {
        "dual_vs_time_only": _mcnemar(root, "time_only", "dual"),
        "dual_vs_time_only_wide": _mcnemar(root, "time_only_wide", "dual"),
        "frequency_only_vs_time_only": _mcnemar(root, "time_only", "frequency_only"),
    }
    report = {
        "overall": overall.to_dict(orient="records"),
        "paired_significance": significance,
        "answers": {
            "frequency_only_minus_time_only_accuracy": float(indexed.loc["frequency_only", "overall_accuracy"] - indexed.loc["time_only", "overall_accuracy"]),
            "dual_minus_time_only_accuracy": float(indexed.loc["dual", "overall_accuracy"] - indexed.loc["time_only", "overall_accuracy"]),
            "dual_minus_time_only_wide_accuracy": float(indexed.loc["dual", "overall_accuracy"] - indexed.loc["time_only_wide", "overall_accuracy"]),
            "dual_minus_time_only_qam_mean_accuracy": float(qam["dual"] - qam["time_only"]),
            "dual_minus_time_only_wide_qam_mean_accuracy": float(qam["dual"] - qam["time_only_wide"]),
            "dual_minus_time_only_low_snr_mean_accuracy": float(low["dual"] - low["time_only"]),
            "dual_minus_time_only_wide_low_snr_mean_accuracy": float(low["dual"] - low["time_only_wide"]),
        },
        "planned_hardware_partition": "DFT/power frontend is planned for FPGA; frontend hardware performance has not been measured or claimed.",
    }
    (tables / "comparison_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/dual_domain_v1.yaml")
    args = parser.parse_args()
    print(json.dumps(compare(args.config), indent=2))


if __name__ == "__main__":
    main()
