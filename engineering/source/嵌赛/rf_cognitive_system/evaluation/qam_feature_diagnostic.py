"""Data-level high-SNR QAM physical-feature sanity checks."""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
import torch

from datasets.synthetic_dataset import SyntheticModulationDataset
from models.qam_aware_rfnet import InstantaneousPower, LagOneCorrelation
from training.qam_aware_utils import load_qam_aware_config
from training.utils import resolve_project_path


def _record_statistics(iq_tensor) -> dict[str, float]:
    i_component = iq_tensor[0].numpy().astype(np.float64)
    q_component = iq_tensor[1].numpy().astype(np.float64)
    power = i_component * i_component + q_component * q_component
    correlation_real = i_component[1:] * i_component[:-1] + q_component[1:] * q_component[:-1]
    correlation_imag = q_component[1:] * i_component[:-1] - i_component[1:] * q_component[:-1]
    correlation_magnitude = np.sqrt(correlation_real**2 + correlation_imag**2)
    return {
        "mean_power": float(np.mean(power)),
        "second_moment_power": float(np.mean(power**2)),
        "power_variance": float(np.var(power)),
        "lag_correlation_magnitude_mean": float(np.mean(correlation_magnitude)),
        "lag_correlation_magnitude_second_moment": float(np.mean(correlation_magnitude**2)),
        "lag_correlation_magnitude_std": float(np.std(correlation_magnitude)),
    }


def run_qam_feature_diagnostic(config_path: str, samples_per_class: int = 250) -> dict[str, object]:
    config = load_qam_aware_config(config_path)
    classes = list(config["signal"]["modulations"])
    qam_indices = {classes.index("16QAM"): "16QAM", classes.index("64QAM"): "64QAM"}
    rows: list[dict[str, float | str]] = []
    for snr in (10.0, 20.0):
        dataset = SyntheticModulationDataset(
            samples_per_class * len(classes), config["signal"], config["channel"], int(config["seed"]),
            f"snr_sweep_{int(snr)}", fixed_snr_db=snr
        )
        for repetition in range(samples_per_class):
            for label, modulation in qam_indices.items():
                tensor, actual_label = dataset[repetition * len(classes) + label]
                if actual_label != label:
                    raise RuntimeError("Unexpected balanced dataset label assignment")
                rows.append({"snr_db": snr, "modulation": modulation, **_record_statistics(tensor)})
    frame = pd.DataFrame(rows)
    metric_columns = [column for column in frame.columns if column not in {"snr_db", "modulation"}]
    aggregate = frame.groupby(["snr_db", "modulation"])[metric_columns].agg(["mean", "std"])
    aggregate.columns = [f"{metric}_{stat}" for metric, stat in aggregate.columns]
    aggregate = aggregate.reset_index()

    differences = []
    for snr in (10.0, 20.0):
        subset = frame[frame["snr_db"] == snr]
        for metric in metric_columns:
            values16 = subset[subset["modulation"] == "16QAM"][metric].to_numpy()
            values64 = subset[subset["modulation"] == "64QAM"][metric].to_numpy()
            pooled = np.sqrt((values16.var(ddof=1) + values64.var(ddof=1)) / 2.0)
            effect = float((values64.mean() - values16.mean()) / pooled) if pooled > 0 else 0.0
            differences.append({
                "snr_db": snr,
                "metric": metric,
                "mean_16qam": float(values16.mean()),
                "mean_64qam": float(values64.mean()),
                "64qam_minus_16qam": float(values64.mean() - values16.mean()),
                "cohens_d_64_minus_16": effect,
            })

    # Exercise raw features across the frozen current-test distribution,
    # including low SNR, to catch overflow or pathological scale before train.
    range_dataset = SyntheticModulationDataset(
        min(512, int(config["dataset"]["test_samples"])),
        config["signal"], config["channel"], int(config["seed"]), "test",
        snr_values=config["dataset"]["snr_values"],
    )
    batch = torch.stack([range_dataset[index][0] for index in range(len(range_dataset))])
    feature_tensors = {
        "power": InstantaneousPower()(batch).numpy(),
        "lag_real": LagOneCorrelation()(batch)[:, 0:1].numpy(),
        "lag_imag": LagOneCorrelation()(batch)[:, 1:2].numpy(),
    }
    range_summary = {}
    for name, values in feature_tensors.items():
        range_summary[name] = {
            "minimum": float(values.min()),
            "maximum": float(values.max()),
            "mean": float(values.mean()),
            "std": float(values.std()),
            "p01": float(np.quantile(values, 0.01)),
            "p99": float(np.quantile(values, 0.99)),
            "all_finite": bool(np.isfinite(values).all()),
        }
    output = resolve_project_path(config["output_root"]) / "diagnostics"
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output / "qam_feature_records.csv", index=False)
    aggregate.to_csv(output / "qam_feature_summary.csv", index=False)
    pd.DataFrame(differences).to_csv(output / "qam_feature_differences.csv", index=False)
    report = {
        "scope": "Existing frozen snr_sweep namespaces at +10/+20 dB; not final_blind_test",
        "samples_per_class_per_snr": samples_per_class,
        "rows": len(frame),
        "all_finite": bool(np.isfinite(frame[metric_columns].to_numpy()).all()),
        "summary": aggregate.to_dict(orient="records"),
        "differences": differences,
        "raw_feature_range_current_test_first_512": range_summary,
    }
    (output / "qam_feature_diagnostic.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v2.yaml")
    parser.add_argument("--samples-per-class", type=int, default=250)
    args = parser.parse_args()
    result = run_qam_feature_diagnostic(args.config, args.samples_per_class)
    print(json.dumps({"rows": result["rows"], "all_finite": result["all_finite"]}, indent=2))


if __name__ == "__main__":
    main()
