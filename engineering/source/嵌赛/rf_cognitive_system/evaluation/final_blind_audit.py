"""Provenance/balance-only audit for the reserved final blind test.

This module intentionally has no model import, prediction, or metric code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from datasets.synthetic_dataset import SyntheticModulationDataset
from training.qam_aware_utils import load_qam_aware_config
from training.utils import resolve_project_path


def _split_code(split: str) -> int:
    return int.from_bytes(hashlib.blake2s(split.encode("utf-8"), digest_size=4).digest(), "little")


def audit_final_blind(config_path: str) -> dict[str, object]:
    config = load_qam_aware_config(config_path)
    blind = config["final_blind_test"]
    seed = int(blind["seed"])
    split = str(blind["split"])
    samples = int(blind["samples"])
    reference_seed = int(config["seed"])
    if seed == reference_seed:
        raise RuntimeError("final_blind_test must use an independent base seed")
    if split in {"train", "validation", "test"} or split.startswith("snr_sweep_"):
        raise RuntimeError("final_blind_test must use an independent split namespace")

    dataset = SyntheticModulationDataset(
        samples,
        config["signal"],
        config["channel"],
        seed,
        split,
        return_metadata=False,
        snr_values=config["dataset"]["snr_values"],
    )
    classes = dataset.modulations
    snrs = [float(value) for value in config["dataset"]["snr_values"]]
    rows = []
    for index in range(len(dataset)):
        combination = index % (len(classes) * len(snrs))
        label = combination % len(classes)
        snr = snrs[combination // len(classes)]
        rows.append({"modulation": classes[label], "snr_db": snr})
    frame = pd.DataFrame(rows)
    class_counts = Counter(frame["modulation"])
    snr_counts = Counter(frame["snr_db"])
    cross = frame.groupby(["modulation", "snr_db"]).size().unstack(fill_value=0)
    expected_cell = samples // (len(classes) * len(snrs))
    balanced = samples % (len(classes) * len(snrs)) == 0 and bool((cross.to_numpy() == expected_cell).all())
    if not balanced:
        raise RuntimeError("final_blind_test is not exactly modulation x SNR balanced")

    namespaces = {
        name: {"base_seed": reference_seed, "split": name, "split_code": _split_code(name)}
        for name in ("train", "validation", "test")
    }
    namespaces["final_blind_test"] = {"base_seed": seed, "split": split, "split_code": _split_code(split)}
    blind_namespace = (seed, _split_code(split))
    overlaps = [
        name for name, info in namespaces.items()
        if name != "final_blind_test" and (info["base_seed"], info["split_code"]) == blind_namespace
    ]
    report = {
        "policy": "BALANCE/PROVENANCE AUDIT ONLY. No model inference or performance metrics were computed.",
        "samples": samples,
        "modulations": classes,
        "snr_values": snrs,
        "samples_per_modulation_snr": expected_cell,
        "class_counts": dict(class_counts),
        "snr_counts": {str(key): value for key, value in snr_counts.items()},
        "balanced": balanced,
        "provenance_namespaces": namespaces,
        "seed_or_split_namespace_overlap": overlaps,
        "leakage_found": bool(overlaps),
        "generation_rule": "SyntheticModulationDataset + frozen signal/channel config; fixed epoch=0 for non-train split.",
    }
    output = resolve_project_path(config["output_root"]) / "final_blind_audit"
    output.mkdir(parents=True, exist_ok=True)
    (output / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    cross.to_csv(output / "modulation_snr_balance.csv")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/qam_aware_v2.yaml")
    args = parser.parse_args()
    print(json.dumps(audit_final_blind(args.config), indent=2))


if __name__ == "__main__":
    main()
