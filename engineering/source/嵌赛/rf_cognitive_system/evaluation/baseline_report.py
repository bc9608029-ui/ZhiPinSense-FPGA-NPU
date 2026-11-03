"""Build the final Baseline V1 summary and requested sanity analyses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from training.utils import ensure_output_dirs, load_config


PAIR_NAMES = (("QPSK", "8PSK"), ("16QAM", "64QAM"), ("2FSK", "CPFSK"))


def _confusion_suffix(snr: int) -> str:
    return f"m{abs(snr)}" if snr < 0 else f"p{snr}"


def _pair_analysis(matrix_path: Path, pairs: tuple[tuple[str, str], ...] = PAIR_NAMES) -> dict[str, dict[str, float]]:
    frame = pd.read_csv(matrix_path, index_col=0)
    result: dict[str, dict[str, float]] = {}
    for first, second in pairs:
        first_total = max(float(frame.loc[first].sum()), 1.0)
        second_total = max(float(frame.loc[second].sum()), 1.0)
        result[f"{first}_vs_{second}"] = {
            f"{first}_as_{second}": float(frame.loc[first, second] / first_total),
            f"{second}_as_{first}": float(frame.loc[second, first] / second_total),
        }
    return result


def build_report(config_path: str) -> dict[str, object]:
    config = load_config(config_path)
    paths = ensure_output_dirs(config["output_dir"])
    history = pd.read_csv(paths["logs"] / "training_history.csv")
    test_metrics = json.loads((paths["tables"] / "test_metrics.json").read_text(encoding="utf-8"))
    run_manifest = json.loads((paths["logs"] / "run_manifest.json").read_text(encoding="utf-8"))
    profile = json.loads((paths["tables"] / "model_profile.json").read_text(encoding="utf-8"))
    snr = pd.read_csv(paths["tables"] / "snr_metrics.csv").sort_values("snr_db")
    per_modulation = pd.read_csv(paths["tables"] / "snr_per_modulation_accuracy.csv")

    best_index = int(history["val_loss"].idxmin())
    best = history.iloc[best_index]
    final = history.iloc[-1]
    train_val_gap = float(best["train_accuracy"] - best["val_accuracy"])
    after_best = history.iloc[best_index + 1 :]
    final_loss_increase = float(final["val_loss"] - best["val_loss"])
    validation_degraded = bool(
        len(after_best) >= 3
        and final_loss_increase > 0.02
        and bool((after_best["val_loss"] > float(best["val_loss"]) + 0.01).all())
    )
    overfitting = bool(train_val_gap > 0.10 or validation_degraded)

    deltas = np.diff(snr["accuracy"].to_numpy())
    knee_index = int(np.argmax(deltas)) if len(deltas) else 0
    knee = {
        "interval_db": [float(snr.iloc[knee_index]["snr_db"]), float(snr.iloc[knee_index + 1]["snr_db"])],
        "accuracy_gain": float(deltas[knee_index]),
    }
    high_snr: dict[str, object] = {}
    pair_confusions: dict[str, object] = {}
    for value in (10, 20):
        overall_row = snr.loc[snr["snr_db"] == value].iloc[0]
        class_rows = per_modulation.loc[per_modulation["snr_db"] == value]
        high_snr[str(value)] = {
            "accuracy": float(overall_row["accuracy"]),
            "macro_f1": float(overall_row["macro_f1"]),
            "per_modulation_accuracy": dict(zip(class_rows["modulation"], class_rows["accuracy"])),
        }
        matrix_path = paths["tables"] / f"confusion_matrix_snr_{_confusion_suffix(value)}.csv"
        pair_confusions[str(value)] = _pair_analysis(matrix_path)

    report: dict[str, object] = {
        "overall_accuracy": test_metrics["overall_accuracy"],
        "macro_f1": test_metrics["macro_f1"],
        "per_class_accuracy": test_metrics["per_class_accuracy"],
        "best_epoch": int(best["epoch"]),
        "epochs_completed": int(len(history)),
        "best_validation_loss": float(best["val_loss"]),
        "best_validation_accuracy": float(best["val_accuracy"]),
        "final_train_accuracy": float(final["train_accuracy"]),
        "final_validation_accuracy": float(final["val_accuracy"]),
        "overfitting_detected": overfitting,
        "overfitting_basis": {
            "accuracy_gap_at_best_epoch": train_val_gap,
            "final_validation_loss_increase_from_best": final_loss_increase,
            "validation_degraded_after_best": validation_degraded,
            "rule": "flag if best-epoch train/validation accuracy gap > 0.10, or at least 3 later epochs remain >0.01 above best and final loss is >0.02 above best",
        },
        "performance_knee": knee,
        "high_snr_sanity": high_snr,
        "selected_pair_confusions": pair_confusions,
        "single_sample_cpu_inference_ms": test_metrics["single_sample_inference_ms"],
        "batch_inference_throughput_records_per_sec": test_metrics["batch_inference_throughput_records_per_sec"],
        "end_to_end_test_records_per_sec": test_metrics["end_to_end_test_records_per_sec"],
        "model_profile": profile,
        "training_time_sec": run_manifest["training_time_sec"],
        "peak_process_rss_mb": run_manifest["peak_process_rss_mb"],
        "environment": test_metrics["environment"],
        "config_file": test_metrics["config_file"],
        "git_commit": test_metrics["git_commit"],
        "random_seed": test_metrics["seed"],
    }
    json_path = paths["tables"] / "baseline_v1_summary.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Baseline V1 summary",
        "",
        f"- Overall accuracy: {report['overall_accuracy']:.6f}",
        f"- Macro-F1: {report['macro_f1']:.6f}",
        f"- Best epoch: {report['best_epoch']}",
        f"- Overfitting detected: {report['overfitting_detected']}",
        f"- Performance knee: {knee['interval_db'][0]:g} to {knee['interval_db'][1]:g} dB",
        f"- Training time: {report['training_time_sec']:.1f} s",
        f"- Peak process RSS: {report['peak_process_rss_mb']:.1f} MB",
        f"- Git commit: {report['git_commit']}",
        "",
        "The JSON companion contains per-class, high-SNR, pair-confusion, latency, throughput, and environment details.",
    ]
    (paths["tables"] / "baseline_v1_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/baseline.yaml")
    args = parser.parse_args()
    print(json.dumps(build_report(args.config), indent=2))


if __name__ == "__main__":
    main()
