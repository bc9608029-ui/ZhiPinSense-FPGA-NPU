"""Validate RadioML 2018.01A and create deterministic leakage-free indices."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from datasets.radioml2018_dataset import read_class_names
from training.utils import load_yaml, resolve_project_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _append(grouped: dict[tuple[int, float], list[np.ndarray]], labels: np.ndarray,
            snrs: np.ndarray, offset: int) -> None:
    for label in np.unique(labels):
        label_mask = labels == label
        for snr in np.unique(snrs[label_mask]):
            positions = np.flatnonzero(label_mask & (snrs == snr)).astype(np.int64) + offset
            grouped[(int(label), float(snr))].append(positions)


def audit(config_or_path: dict[str, Any] | str) -> dict[str, Any]:
    config = config_or_path if isinstance(config_or_path, dict) else load_yaml(config_or_path)
    public = config["public_data"]
    hdf5_path = resolve_project_path(public["hdf5_path"])
    classes_path = resolve_project_path(public["classes_path"])
    audit_path = resolve_project_path(public["audit_path"])
    index_path = resolve_project_path(public["index_path"])
    if not hdf5_path.is_file():
        raise FileNotFoundError(
            f"RadioML 2018.01A HDF5 is missing: {hdf5_path}. Synthetic fallback is forbidden."
        )
    class_names = read_class_names(classes_path)
    ratios = [float(value) for value in public.get("split_ratios", [0.6, 0.2, 0.2])]
    if len(ratios) != 3 or not np.isclose(sum(ratios), 1.0) or any(value <= 0 for value in ratios):
        raise ValueError("public_data.split_ratios must be three positive values summing to one")
    seed = int(public.get("split_seed", 20261003))
    chunk_size = int(public.get("audit_chunk_size", 65536))
    x_chunk_size = int(public.get("x_audit_chunk_size", 2048))
    if chunk_size <= 0 or x_chunk_size <= 0:
        raise ValueError("RadioML audit chunk sizes must be positive")
    grouped: dict[tuple[int, float], list[np.ndarray]] = defaultdict(list)

    with h5py.File(hdf5_path, "r") as handle:
        if not {"X", "Y", "Z"}.issubset(handle.keys()):
            raise RuntimeError(f"RadioML HDF5 must contain X/Y/Z, found {sorted(handle.keys())}")
        x, y, z = handle["X"], handle["Y"], handle["Z"]
        if x.ndim != 3 or tuple(x.shape[1:]) != (1024, 2):
            raise RuntimeError(f"RadioML X must have shape [N,1024,2], received {x.shape}")
        if y.ndim != 2 or y.shape != (x.shape[0], len(class_names)):
            raise RuntimeError(f"RadioML Y shape does not match X/classes: X={x.shape}, Y={y.shape}")
        if z.shape[0] != x.shape[0]:
            raise RuntimeError(f"RadioML Z length does not match X: X={x.shape}, Z={z.shape}")
        total = int(x.shape[0])
        for start in range(0, total, x_chunk_size):
            stop = min(start + x_chunk_size, total)
            if not np.isfinite(np.asarray(x[start:stop])).all():
                raise RuntimeError(f"non-finite RadioML IQ in rows {start}:{stop}")
        for start in range(0, total, chunk_size):
            stop = min(start + chunk_size, total)
            labels_raw = np.asarray(y[start:stop])
            snrs = np.asarray(z[start:stop], dtype=np.float32).reshape(-1)
            if not np.isfinite(labels_raw).all() or not np.isfinite(snrs).all():
                raise RuntimeError(f"non-finite RadioML labels/SNR in rows {start}:{stop}")
            if not np.allclose(labels_raw.sum(axis=1), 1.0, atol=1e-5):
                raise RuntimeError(f"RadioML Y is not one-hot in rows {start}:{stop}")
            binary = np.isclose(labels_raw, 0.0, atol=1e-6) | np.isclose(labels_raw, 1.0, atol=1e-6)
            if not bool(binary.all()) or not bool((np.isclose(labels_raw, 1.0, atol=1e-6).sum(axis=1) == 1).all()):
                raise RuntimeError(f"RadioML Y contains non-binary or multi-hot labels in rows {start}:{stop}")
            labels = labels_raw.argmax(axis=1).astype(np.int64)
            _append(grouped, labels, snrs, start)

    if len(grouped) != len(class_names) * 26:
        raise RuntimeError(
            f"expected 24 classes x 26 SNR strata, found {len(grouped)}; refusing ambiguous data"
        )
    expected_samples = public.get("expected_samples", 2_555_904)
    if expected_samples is not None and total != int(expected_samples):
        raise RuntimeError(
            f"expected {int(expected_samples)} RadioML rows, found {total}; refusing partial data"
        )
    expected_snrs = {
        float(value) for value in public.get("expected_snr_values", range(-20, 31, 2))
    }
    actual_snrs = {snr for _label, snr in grouped}
    if actual_snrs != expected_snrs:
        raise RuntimeError(
            f"RadioML SNR grid mismatch; expected={sorted(expected_snrs)}, "
            f"received={sorted(actual_snrs)}"
        )
    expected_per_stratum = public.get("expected_per_stratum", 4096)
    if expected_per_stratum is not None:
        invalid = {
            f"{class_names[label]}@{snr:g}": sum(len(piece) for piece in pieces)
            for (label, snr), pieces in grouped.items()
            if sum(len(piece) for piece in pieces) != int(expected_per_stratum)
        }
        if invalid:
            preview = dict(list(sorted(invalid.items()))[:8])
            raise RuntimeError(
                f"RadioML strata are incomplete; expected {int(expected_per_stratum)} each, "
                f"first mismatches={preview}"
            )

    output: dict[str, list[np.ndarray]] = {
        "train_indices": [], "train_labels": [], "train_snrs": [],
        "validation_indices": [], "validation_labels": [], "validation_snrs": [],
        "test_indices": [], "test_labels": [], "test_snrs": [],
    }
    strata: dict[str, int] = {}
    for (label, snr), pieces in sorted(grouped.items()):
        indices = np.concatenate(pieces)
        rng = np.random.default_rng(np.random.SeedSequence([seed, label, int(round(snr)) + 128]))
        rng.shuffle(indices)
        train_count = int(len(indices) * ratios[0])
        validation_count = int(len(indices) * ratios[1])
        split_arrays = {
            "train": indices[:train_count],
            "validation": indices[train_count:train_count + validation_count],
            "test": indices[train_count + validation_count:],
        }
        strata[f"{class_names[label]}@{snr:g}"] = len(indices)
        for split, values in split_arrays.items():
            output[f"{split}_indices"].append(values)
            output[f"{split}_labels"].append(np.full(len(values), label, dtype=np.int64))
            output[f"{split}_snrs"].append(np.full(len(values), snr, dtype=np.float32))

    arrays = {name: np.concatenate(values) for name, values in output.items()}
    train_set = set(arrays["train_indices"].tolist())
    validation_set = set(arrays["validation_indices"].tolist())
    test_set = set(arrays["test_indices"].tolist())
    if train_set & validation_set or train_set & test_set or validation_set & test_set:
        raise RuntimeError("RadioML split overlap detected")
    if len(train_set | validation_set | test_set) != total:
        raise RuntimeError("RadioML split union does not cover every source row exactly once")

    index_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(index_path, **arrays)
    digest = _sha256(hdf5_path)
    report = {
        "status": "pass",
        "dataset": "RadioML2018.01A",
        "hdf5_path": str(hdf5_path),
        "size_bytes": hdf5_path.stat().st_size,
        "mtime_ns": hdf5_path.stat().st_mtime_ns,
        "sha256": digest,
        "class_names": list(class_names),
        "sample_shape": [1024, 2],
        "samples": total,
        "split_seed": seed,
        "split_ratios": ratios,
        "split_counts": {
            split: int(len(arrays[f"{split}_indices"]))
            for split in ("train", "validation", "test")
        },
        "strata_counts": strata,
        "index_path": str(index_path),
        "index_sha256": _sha256(index_path),
        "overlap_counts": {"train_validation": 0, "train_test": 0, "validation_test": 0},
        "synthetic_fallback": False,
    }
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ad_amr_v1_1_data_v2.yaml")
    args = parser.parse_args()
    report = audit(args.config)
    print(json.dumps({
        "status": report["status"], "sha256": report["sha256"],
        "samples": report["samples"], "split_counts": report["split_counts"],
    }, indent=2))
    print("AD_AMR_V1_1_RADIOML_AUDIT_PASS")


if __name__ == "__main__":
    main()
