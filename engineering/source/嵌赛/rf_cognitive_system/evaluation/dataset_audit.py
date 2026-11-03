"""Generate reproducible Dataset Audit V1 tables before formal training."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from datasets.modulation_generator import generate_iq
from datasets.synthetic_dataset import SyntheticModulationDataset
from training.utils import ensure_output_dirs, load_config


def _dataset_distribution(num_samples: int, classes: list[str], snrs: list[float]) -> tuple[Counter, Counter, Counter]:
    class_counts: Counter = Counter()
    snr_counts: Counter = Counter()
    pair_counts: Counter = Counter()
    combinations = len(classes) * len(snrs)
    for index in range(num_samples):
        combination = index % combinations
        modulation = classes[combination % len(classes)]
        snr = float(snrs[combination // len(classes)])
        class_counts[modulation] += 1
        snr_counts[snr] += 1
        pair_counts[(modulation, snr)] += 1
    return class_counts, snr_counts, pair_counts


def _fingerprints(config: dict[str, Any], split: str, count: int = 64) -> set[str]:
    dataset = SyntheticModulationDataset(
        count,
        config["signal"],
        None,
        seed=int(config["seed"]),
        split=split,
        snr_values=config["dataset"].get("snr_values"),
    )
    return {hashlib.sha256(dataset[index][0].numpy().tobytes()).hexdigest() for index in range(count)}


def run_dataset_audit(config: dict[str, Any]) -> dict[str, Any]:
    paths = ensure_output_dirs(config["output_dir"])
    classes = list(config["signal"]["modulations"])
    snrs = [float(value) for value in config["dataset"]["snr_values"]]
    class_rows: list[dict[str, object]] = []
    snr_rows: list[dict[str, object]] = []
    pair_rows: list[dict[str, object]] = []
    split_counts: dict[str, tuple[Counter, Counter, Counter]] = {}
    for split, key in (("train", "train_samples"), ("validation", "val_samples"), ("test", "test_samples")):
        counts = _dataset_distribution(int(config["dataset"][key]), classes, snrs)
        split_counts[split] = counts
        class_rows.extend({"split": split, "modulation": name, "count": counts[0][name]} for name in classes)
        snr_rows.extend({"split": split, "snr_db": snr, "count": counts[1][snr]} for snr in snrs)
        pair_rows.extend(
            {"split": split, "snr_db": snr, "modulation": name, "count": counts[2][(name, snr)]}
            for snr in snrs
            for name in classes
        )
    pd.DataFrame(class_rows).to_csv(paths["tables"] / "dataset_class_counts.csv", index=False)
    pd.DataFrame(snr_rows).to_csv(paths["tables"] / "dataset_snr_counts.csv", index=False)
    pair_frame = pd.DataFrame(pair_rows)
    pair_frame.to_csv(paths["tables"] / "modulation_snr_distribution.csv", index=False)
    pair_frame.pivot_table(index=["split", "snr_db"], columns="modulation", values="count").to_csv(
        paths["tables"] / "modulation_snr_pivot.csv"
    )

    statistics_rows: list[dict[str, object]] = []
    audit_count = int(config.get("audit", {}).get("samples_per_modulation", 128))
    for class_index, modulation in enumerate(classes):
        powers: list[float] = []
        rms_values: list[float] = []
        papr_values: list[float] = []
        boundary_ratios: list[float] = []
        bandwidths: list[float] = []
        offsets: list[int] = []
        for sample_index in range(audit_count):
            rng = np.random.default_rng(np.random.SeedSequence([int(config["seed"]), 0xA0D17, class_index, sample_index]))
            iq, metadata = generate_iq(modulation, config["signal"], rng)
            power = float(np.mean(np.abs(iq) ** 2))
            powers.append(power)
            rms_values.append(float(np.sqrt(power)))
            papr_values.append(float(10.0 * np.log10(np.max(np.abs(iq) ** 2) / power)))
            edge = max(8, len(iq) // 16)
            edge_power = float(np.mean(np.abs(np.concatenate((iq[:edge], iq[-edge:]))) ** 2))
            center_power = float(np.mean(np.abs(iq[edge:-edge]) ** 2))
            boundary_ratios.append(edge_power / max(center_power, 1e-12))
            if "occupied_bandwidth_hz_approx" in metadata:
                bandwidths.append(float(metadata["occupied_bandwidth_hz_approx"]))
            offset = metadata.get("record_timing_offset_samples", metadata.get("record_offset_within_ofdm_symbol", 0))
            offsets.append(int(offset))
        statistics_rows.append(
            {
                "modulation": modulation,
                "samples": audit_count,
                "mean_signal_power": np.mean(powers),
                "mean_rms": np.mean(rms_values),
                "papr_mean_db": np.mean(papr_values),
                "papr_std_db": np.std(papr_values),
                "papr_p95_db": np.percentile(papr_values, 95),
                "boundary_to_center_power_mean": np.mean(boundary_ratios),
                "occupied_bandwidth_hz_approx": np.mean(bandwidths) if bandwidths else None,
                "unique_record_offsets": len(set(offsets)),
                "sample_length": int(config["signal"]["sample_length"]),
            }
        )
    statistics = pd.DataFrame(statistics_rows)
    statistics.to_csv(paths["tables"] / "modulation_signal_statistics.csv", index=False)

    fingerprints = {split: _fingerprints(config, split) for split in ("train", "validation", "test")}
    overlaps = {
        "train_validation": len(fingerprints["train"] & fingerprints["validation"]),
        "train_test": len(fingerprints["train"] & fingerprints["test"]),
        "validation_test": len(fingerprints["validation"] & fingerprints["test"]),
    }
    count_balance = {
        split: {
            "class_min": min(counts[0].values()),
            "class_max": max(counts[0].values()),
            "snr_min": min(counts[1].values()),
            "snr_max": max(counts[1].values()),
            "pair_min": min(counts[2].values()),
            "pair_max": max(counts[2].values()),
        }
        for split, counts in split_counts.items()
    }
    rrc_bandwidth = float((1.0 + config["signal"]["pulse_shape"]["rolloff"]) * config["signal"]["symbol_rate"])
    ofdm_bandwidth = float(
        config["signal"]["ofdm"]["active_subcarriers"]
        * config["signal"]["sample_rate"]
        / config["signal"]["ofdm"]["fft_length"]
    )
    findings: list[dict[str, str]] = []
    if any(value for value in overlaps.values()):
        findings.append({"severity": "error", "finding": f"Exact waveform overlap detected: {overlaps}"})
    if any(item["class_min"] != item["class_max"] or item["pair_min"] != item["pair_max"] for item in count_balance.values()):
        findings.append({"severity": "error", "finding": "A split is not exactly class/SNR balanced."})
    power_span = float(statistics["mean_signal_power"].max() - statistics["mean_signal_power"].min())
    if power_span > 1e-3:
        findings.append({"severity": "warning", "finding": f"Class mean-power span is {power_span:.3g}."})
    if max(ofdm_bandwidth / rrc_bandwidth, rrc_bandwidth / ofdm_bandwidth) > 1.5:
        findings.append({"severity": "warning", "finding": "OFDM/RRC occupied bandwidth differs by more than 1.5x."})
    findings.append(
        {
            "severity": "note",
            "finding": "Constant-envelope FSK and OFDM CP/PAPR/cyclostationarity are legitimate modulation properties, but models may rely heavily on them; report per-class results.",
        }
    )
    findings.append(
        {
            "severity": "note",
            "finding": "All classes use randomized record-start timing. OFDM occupied bandwidth is approximately matched to RRC single-carrier bandwidth.",
        }
    )
    report: dict[str, Any] = {
        "config": config["_config_path"],
        "base_seed": int(config["seed"]),
        "generation_strategy": {
            "train": "deterministic on-the-fly; SeedSequence[base_seed, split_hash, epoch, index]; epoch changes",
            "validation": "fixed on-the-fly; split-specific SeedSequence; set_epoch ignored",
            "test": "fixed on-the-fly; split-specific SeedSequence; set_epoch ignored",
            "labels_and_snr": "cyclic exact stratification over modulation x configured discrete SNR grid",
        },
        "count_balance": count_balance,
        "fingerprint_overlap_first_64": overlaps,
        "mean_power_span": power_span,
        "rrc_occupied_bandwidth_hz_approx": rrc_bandwidth,
        "ofdm_occupied_bandwidth_hz_approx": ofdm_bandwidth,
        "findings": findings,
        "blocking_leakage_found": any(item["severity"] == "error" for item in findings),
    }
    (paths["tables"] / "dataset_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    markdown = [
        "# Dataset Audit V1",
        "",
        f"- Config: `{config['_config_path']}`",
        f"- Base seed: `{config['seed']}`",
        f"- Exact overlap in first 64 records per split: `{overlaps}`",
        f"- Blocking leakage found: `{report['blocking_leakage_found']}`",
        f"- RRC/OFDM occupied bandwidth estimate: `{rrc_bandwidth:.1f}` / `{ofdm_bandwidth:.1f}` Hz",
        "",
        "## Findings",
        "",
        *[f"- **{item['severity']}**: {item['finding']}" for item in findings],
        "",
        "See the adjacent CSV files for class, SNR, modulation x SNR, power, RMS, PAPR, boundary, and timing-offset statistics.",
    ]
    (paths["tables"] / "dataset_audit.md").write_text("\n".join(markdown), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/baseline.yaml")
    args = parser.parse_args()
    report = run_dataset_audit(load_config(args.config))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

