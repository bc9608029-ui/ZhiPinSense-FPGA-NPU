"""Compare frozen controls with QAM-Aware V2 on development evidence only."""

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
from sklearn.metrics import f1_score

from training.qam_aware_utils import load_qam_aware_config
from training.utils import PROJECT_ROOT, resolve_project_path


KEY_SNRS = (-12, -10, -8, -6, -4, 0, 10, 20)
CLASSES = ("BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM")
CONTROL_PATHS = {
    "baseline_v1": PROJECT_ROOT / "outputs" / "baseline_v1",
    "time_only": PROJECT_ROOT / "outputs" / "dual_domain_v1" / "time_only",
    "time_only_wide": PROJECT_ROOT / "outputs" / "dual_domain_v1" / "time_only_wide",
    "dual": PROJECT_ROOT / "outputs" / "dual_domain_v1" / "dual",
}


def _read_control(name: str, root: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metric_name = "test_metrics.json"
    metrics = json.loads((root / "tables" / metric_name).read_text(encoding="utf-8"))
    matrix = pd.read_csv(root / "tables" / "confusion_matrix.csv", index_col=0).to_numpy()
    true_labels = np.repeat(np.arange(len(CLASSES)), matrix.sum(axis=1).astype(int))
    predicted_labels = np.concatenate([
        np.repeat(np.arange(len(CLASSES)), matrix[row].astype(int)) for row in range(len(CLASSES))
    ])
    per_f1 = f1_score(true_labels, predicted_labels, labels=np.arange(len(CLASSES)), average=None, zero_division=0)
    per_class = pd.DataFrame({
        "modulation": CLASSES,
        "accuracy": [metrics["per_class_accuracy"][name] for name in CLASSES],
        "f1": per_f1,
    })
    snr = pd.read_csv(root / "tables" / "snr_metrics.csv")
    per_snr = pd.read_csv(root / "tables" / "snr_per_modulation_accuracy.csv")
    per_snr["f1"] = np.nan
    overall = {
        "model": name,
        "overall_accuracy": metrics["overall_accuracy"],
        "macro_f1": metrics["macro_f1"],
    }
    return overall, per_class, snr, per_snr


def _read_v2(name: str, root: Path) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics = json.loads((root / name / "tables" / "evaluation.json").read_text(encoding="utf-8"))
    overall = {"model": name, "overall_accuracy": metrics["overall_accuracy"], "macro_f1": metrics["macro_f1"]}
    return (
        overall,
        pd.read_csv(root / name / "tables" / "development_per_class.csv"),
        pd.read_csv(root / name / "tables" / "snr_metrics.csv"),
        pd.read_csv(root / name / "tables" / "snr_per_modulation_metrics.csv"),
        pd.read_csv(root / name / "tables" / "qam_snr_diagnostics.csv"),
    )


def _paired_result(reference: pd.DataFrame, candidate: pd.DataFrame, mask: np.ndarray) -> dict[str, float | int | bool]:
    reference_correct = reference["predicted_label"].to_numpy() == reference["true_label"].to_numpy()
    candidate_correct = candidate["predicted_label"].to_numpy() == candidate["true_label"].to_numpy()
    ref_only = int(np.sum(reference_correct[mask] & ~candidate_correct[mask]))
    candidate_only = int(np.sum(~reference_correct[mask] & candidate_correct[mask]))
    discordant = ref_only + candidate_only
    p_value = float(binomtest(min(ref_only, candidate_only), discordant, 0.5).pvalue) if discordant else 1.0
    return {
        "reference_only_correct": ref_only,
        "candidate_only_correct": candidate_only,
        "discordant": discordant,
        "exact_two_sided_p_value": p_value,
        "candidate_significantly_better_at_0_05": bool(candidate_only > ref_only and p_value < 0.05),
    }


def compare(config_path: str) -> dict[str, object]:
    config = load_qam_aware_config(config_path)
    root = resolve_project_path(config["output_root"])
    output = root / "comparison"
    figures, tables = output / "figures", output / "tables"
    figures.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    overall_rows, per_class_frames, snr_frames, per_snr_frames = [], [], [], []
    qam_diagnostics: dict[str, pd.DataFrame] = {}

    for name, path in CONTROL_PATHS.items():
        overall, per_class, snr, per_snr = _read_control(name, path)
        overall_rows.append(overall)
        per_class["model"] = name
        snr["model"] = name
        per_snr["model"] = name
        per_class_frames.append(per_class)
        snr_frames.append(snr)
        per_snr_frames.append(per_snr)
    for name in config["variants"]:
        overall, per_class, snr, per_snr, qam = _read_v2(name, root)
        overall_rows.append(overall)
        per_class["model"] = name
        snr["model"] = name
        per_snr["model"] = name
        per_class_frames.append(per_class)
        snr_frames.append(snr)
        per_snr_frames.append(per_snr)
        qam_diagnostics[name] = qam

    overall = pd.DataFrame(overall_rows)
    per_class = pd.concat(per_class_frames, ignore_index=True)
    snr = pd.concat(snr_frames, ignore_index=True)
    per_snr = pd.concat(per_snr_frames, ignore_index=True)
    overall.to_csv(tables / "overall_comparison.csv", index=False)
    per_class.to_csv(tables / "per_class_comparison.csv", index=False)
    snr[snr["snr_db"].isin(KEY_SNRS)].to_csv(tables / "key_snr_comparison.csv", index=False)

    qam_rows = []
    for model in overall["model"]:
        selected = per_snr[(per_snr["model"] == model) & per_snr["modulation"].isin(["16QAM", "64QAM"])]
        high = selected[selected["snr_db"].isin([0, 10, 20])]
        for _, row in high.iterrows():
            qam_rows.append({
                "model": model, "snr_db": row["snr_db"], "modulation": row["modulation"],
                "accuracy": row["accuracy"], "qam_high_snr_mean": float(high["accuracy"].mean())
            })
    qam_frame = pd.DataFrame(qam_rows)
    for model, frame in qam_diagnostics.items():
        for column in ("16qam_to_64qam_rate", "64qam_to_16qam_rate"):
            mapping = frame.set_index("snr_db")[column]
            qam_frame.loc[qam_frame["model"] == model, column] = qam_frame.loc[
                qam_frame["model"] == model, "snr_db"
            ].map(mapping)
    qam_frame.to_csv(tables / "qam_comparison.csv", index=False)

    wide = pd.read_csv(CONTROL_PATHS["time_only_wide"] / "tables" / "test_predictions.csv").rename(
        columns={"index": "sample_index", "target": "true_label", "prediction": "predicted_label"}
    )
    mcnemar = {}
    for name in config["variants"]:
        candidate = pd.read_csv(root / name / "tables" / "development_test_predictions.csv")
        reference = wide.iloc[: len(candidate)].reset_index(drop=True)
        if not np.array_equal(reference["sample_index"], candidate["sample_index"]):
            raise RuntimeError("Development sample index order differs from TimeOnlyWide")
        if not np.array_equal(reference["true_label"], candidate["true_label"]):
            raise RuntimeError("Development true labels differ from TimeOnlyWide")
        labels = candidate["true_label"].to_numpy()
        mcnemar[name] = {
            "all_development_test": _paired_result(reference, candidate, np.ones(len(candidate), dtype=bool)),
            "qam_combined": _paired_result(reference, candidate, np.isin(labels, [3, 4])),
            "16qam_only": _paired_result(reference, candidate, labels == 3),
            "64qam_only": _paired_result(reference, candidate, labels == 4),
        }
    result = {
        "scope": "Development evidence only; p-values are not confirmatory. final_blind_test was not accessed.",
        "reference": "time_only_wide",
        "tests": mcnemar,
    }
    (tables / "mcnemar_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    for metric, filename in (("accuracy", "snr_accuracy_comparison.png"), ("macro_f1", "snr_f1_comparison.png")):
        figure, axis = plt.subplots(figsize=(10, 6))
        for model in overall["model"]:
            subset = snr[snr["model"] == model]
            axis.plot(subset["snr_db"], subset[metric], marker="o", markersize=3, label=model)
        axis.set(xlabel="SNR (dB)", ylabel=metric, ylim=(0, 1.02), title=f"Development {metric} versus SNR")
        axis.grid(True, alpha=0.3)
        axis.legend(fontsize=8, ncol=2)
        figure.tight_layout()
        figure.savefig(figures / filename, dpi=180)
        plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for axis, modulation in zip(axes, ("16QAM", "64QAM")):
        for model in ("time_only_wide", *config["variants"]):
            subset = per_snr[(per_snr["model"] == model) & (per_snr["modulation"] == modulation)]
            axis.plot(subset["snr_db"], subset["accuracy"], marker="o", markersize=3, label=model)
        axis.set(xlabel="SNR (dB)", ylabel="Accuracy", ylim=(0, 1.02), title=modulation)
        axis.grid(True, alpha=0.3)
    axes[0].legend(fontsize=8)
    figure.suptitle("QAM-aware V2 versus capacity-matched TimeOnlyWide")
    figure.tight_layout()
    figure.savefig(figures / "qam_accuracy_comparison.png", dpi=180)
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9, 5))
    for model, frame in qam_diagnostics.items():
        focus = frame[frame["snr_db"].isin([0, 10, 20])]
        axis.plot(
            focus["snr_db"], focus["16qam_to_64qam_rate"], marker="o",
            label=f"{model}: 16QAM→64QAM"
        )
        axis.plot(
            focus["snr_db"], focus["64qam_to_16qam_rate"], marker="s", linestyle="--",
            label=f"{model}: 64QAM→16QAM"
        )
    axis.set(
        xlabel="SNR (dB)", ylabel="Directed confusion rate", ylim=(0, 1.02),
        title="QAM directed confusion at 0/+10/+20 dB"
    )
    axis.grid(True, alpha=0.3)
    axis.legend(fontsize=8, ncol=2)
    figure.tight_layout()
    figure.savefig(figures / "qam_confusion_comparison.png", dpi=180)
    plt.close(figure)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v2.yaml")
    args = parser.parse_args()
    print(json.dumps(compare(args.config), indent=2))


if __name__ == "__main__":
    main()
