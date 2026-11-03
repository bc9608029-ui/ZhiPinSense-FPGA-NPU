"""Fail-closed, leakage-audited RadioML 2018.01A access.

The public corpus is intentionally never replaced by synthetic samples.  A
separate audit step creates deterministic train/validation/test index arrays;
training can only start from that audited index file.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import torch
from torch.utils.data import Dataset

from training.utils import resolve_project_path


OFFICIAL_CLASS_ORDER = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)
SPLITS = ("train", "validation", "test")


def read_class_names(path: str | Path) -> tuple[str, ...]:
    source = resolve_project_path(path)
    if not source.is_file():
        raise FileNotFoundError(f"RadioML class list is missing: {source}")
    text = source.read_text(encoding="utf-8").strip()
    if not text:
        raise RuntimeError(f"RadioML class list is empty: {source}")
    values: list[str]
    if text.startswith("[") or text.startswith("("):
        parsed = ast.literal_eval(text)
        if not isinstance(parsed, (list, tuple)):
            raise RuntimeError("RadioML class list literal must be a list or tuple")
        values = [str(value).strip().upper() for value in parsed]
    else:
        values = [line.strip().strip("',\"").upper() for line in text.splitlines() if line.strip()]
    result = tuple(values)
    if len(result) != 24 or len(set(result)) != 24:
        raise RuntimeError(f"RadioML 2018.01A requires 24 unique class names, received {len(result)}")
    if result != OFFICIAL_CLASS_ORDER:
        raise RuntimeError(
            "RadioML class order differs from the frozen 2018.01A label order; "
            f"expected={OFFICIAL_CLASS_ORDER}, received={result}"
        )
    return result


def load_audit(path: str | Path) -> dict[str, Any]:
    source = resolve_project_path(path)
    if not source.is_file():
        raise FileNotFoundError(
            f"RadioML audit is missing: {source}. Run scripts.audit_radioml2018 first."
        )
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("status") != "pass" or payload.get("dataset") != "RadioML2018.01A":
        raise RuntimeError(f"RadioML audit is not a passing 2018.01A audit: {source}")
    return payload


class RadioML2018Dataset(Dataset):
    """Lazy HDF5 dataset backed exclusively by audited indices."""

    def __init__(
        self,
        hdf5_path: str | Path,
        classes_path: str | Path,
        audit_path: str | Path,
        index_path: str | Path,
        split: str,
        *,
        max_per_stratum: int | None = None,
        allowed_snrs: list[float] | tuple[float, ...] | None = None,
    ) -> None:
        if split not in SPLITS:
            raise ValueError(f"split must be one of {SPLITS}, received {split!r}")
        self.hdf5_path = resolve_project_path(hdf5_path)
        self.classes_path = resolve_project_path(classes_path)
        self.audit_path = resolve_project_path(audit_path)
        self.index_path = resolve_project_path(index_path)
        for source in (self.hdf5_path, self.classes_path, self.audit_path, self.index_path):
            if not source.is_file():
                raise FileNotFoundError(f"required public-data artifact is missing: {source}")
        self.class_names = read_class_names(self.classes_path)
        audit = load_audit(self.audit_path)
        if tuple(audit.get("class_names", [])) != self.class_names:
            raise RuntimeError("class order differs between RadioML audit and classes file")
        stat = self.hdf5_path.stat()
        if int(audit.get("size_bytes", -1)) != stat.st_size:
            raise RuntimeError("RadioML HDF5 size differs from the audited artifact")
        if int(audit.get("mtime_ns", -1)) != stat.st_mtime_ns:
            raise RuntimeError("RadioML HDF5 modification time differs; rerun the data audit")
        if Path(str(audit.get("index_path", ""))).resolve() != self.index_path.resolve():
            raise RuntimeError("RadioML index path differs from the audited artifact")
        expected_index_hash = str(audit.get("index_sha256", ""))
        if len(expected_index_hash) != 64:
            raise RuntimeError("RadioML audit has no valid index SHA-256")
        actual_index_hash = hashlib.sha256(self.index_path.read_bytes()).hexdigest()
        if actual_index_hash != expected_index_hash:
            raise RuntimeError("RadioML index SHA-256 differs from the audited artifact")

        with np.load(self.index_path, allow_pickle=False) as indices:
            required = (f"{split}_indices", f"{split}_labels", f"{split}_snrs")
            missing = [name for name in required if name not in indices]
            if missing:
                raise RuntimeError(f"RadioML index file is missing arrays: {missing}")
            selected_indices = indices[required[0]].astype(np.int64, copy=True)
            selected_labels = indices[required[1]].astype(np.int64, copy=True)
            selected_snrs = indices[required[2]].astype(np.float32, copy=True)
        if not (len(selected_indices) == len(selected_labels) == len(selected_snrs)):
            raise RuntimeError("RadioML index arrays have inconsistent lengths")
        if len(np.unique(selected_indices)) != len(selected_indices):
            raise RuntimeError(f"duplicate RadioML indices found in {split}")

        mask = np.ones(len(selected_indices), dtype=bool)
        if allowed_snrs is not None:
            allowed = np.asarray([float(value) for value in allowed_snrs], dtype=np.float32)
            mask &= np.isin(selected_snrs, allowed)
        selected_indices = selected_indices[mask]
        selected_labels = selected_labels[mask]
        selected_snrs = selected_snrs[mask]

        if max_per_stratum is not None:
            limit = int(max_per_stratum)
            if limit <= 0:
                raise ValueError("max_per_stratum must be positive")
            keep: list[np.ndarray] = []
            for label in range(len(self.class_names)):
                for snr in sorted(set(float(value) for value in selected_snrs.tolist())):
                    positions = np.flatnonzero((selected_labels == label) & (selected_snrs == snr))
                    keep.append(positions[:limit])
            chosen = np.concatenate(keep) if keep else np.empty(0, dtype=np.int64)
            selected_indices = selected_indices[chosen]
            selected_labels = selected_labels[chosen]
            selected_snrs = selected_snrs[chosen]
        if len(selected_indices) == 0:
            raise RuntimeError(f"RadioML {split} selection is empty")

        self.split = split
        self.indices = selected_indices
        self.labels = selected_labels
        self.snrs = selected_snrs
        self._handle: h5py.File | None = None
        self._x: Any = None

    def __len__(self) -> int:
        return len(self.indices)

    def set_epoch(self, _epoch: int) -> None:
        # Public data is immutable; the method keeps compatibility with the V1.1 trainer.
        return None

    def _dataset(self):
        if self._handle is None:
            self._handle = h5py.File(self.hdf5_path, "r")
            self._x = self._handle["X"]
        return self._x

    def __getitem__(self, item: int) -> dict[str, Any]:
        source_index = int(self.indices[item])
        raw = np.asarray(self._dataset()[source_index], dtype=np.float32)
        if raw.shape != (1024, 2):
            raise RuntimeError(f"unexpected RadioML sample shape {raw.shape} at index {source_index}")
        iq = torch.from_numpy(np.ascontiguousarray(raw.T))
        if not bool(torch.isfinite(iq).all()):
            raise RuntimeError(f"non-finite RadioML sample at index {source_index}")
        return {
            "clean_iq": iq,
            "noisy_iq": iq,
            "label": int(self.labels[item]),
            "snr_db": float(self.snrs[item]),
            "sample_id": source_index,
            "split": f"radioml2018_{self.split}",
            "seed": 0,
        }

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_handle"] = None
        state["_x"] = None
        return state

    def close(self) -> None:
        if getattr(self, "_handle", None) is not None:
            self._handle.close()
            self._handle = None
            self._x = None

    def __del__(self) -> None:
        self.close()
