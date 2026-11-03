"""Frozen helpers for the clean generated-v2 RadioML-format RF test."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


LABELS = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)
FIXED_SCALE = 68.46059377833956
PEAK_LIMIT = 1600.0
FRAME_COMPLEX = 16384
RECEIVER_HASHES = {
    "pilot_recovery.py": "d7538a1e27b65cd6b712607b485f1e07de447467bbfdbb04ce67143f9d797713",
    "board_live_rx.py": "2baa4523ff4ae500b10e6fe239f2d3c24bbfbb3185868e202319de3e0eb95107",
    "pluto_link_probe.py": "1b248f8f391976513c35ca54f31d7daef3fa363e2d095940f9ff17d4d60126a2",
    "npu_stream.cpp": "4cfe02f8c72c51e410796c723e4b18f6d17e9bf33b349906991704fee67813df",
    "run_board.sh": "f3c720dbac3f991bc786fc43067938001139f4bb6442765aca5d4bb27800c797",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_receiver(rescue_root: Path) -> dict[str, str]:
    actual = {}
    for name, expected in RECEIVER_HASHES.items():
        path = rescue_root / name
        if not path.is_file():
            raise FileNotFoundError(f"missing frozen receiver file: {path}")
        actual[name] = sha256_file(path)
        if actual[name] != expected:
            raise RuntimeError(f"receiver SHA mismatch: {name}: {actual[name]} != {expected}")
    return actual


def load_public_pilots(rescue_root: Path) -> tuple[np.ndarray, np.ndarray]:
    path = rescue_root / "pilot_recovery.py"
    spec = importlib.util.spec_from_file_location("clean_v2_frozen_pilot_recovery", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    train = np.asarray(module.train, dtype=np.complex64)
    tail = np.asarray(module.tail, dtype=np.complex64)
    if train.shape != (2048,) or tail.shape != (2048,):
        raise RuntimeError(f"unexpected public pilot shapes: {train.shape}, {tail.shape}")
    return train, tail


@dataclass(frozen=True)
class CleanSample:
    source_index: int
    class_index: int
    class_name: str
    seed: int
    source_sha256: str
    source: np.ndarray
    digital_pred: int
    digital_correct: bool


def load_clean_samples(asset_root: Path) -> list[CleanSample]:
    manifest_path = asset_root / "tx_package" / "public_protocol_tx_manifest.tsv"
    baseline_path = asset_root / "baseline" / "v2_digital_baseline_frozen.json"
    rows = list(csv.DictReader(manifest_path.open(encoding="utf-8", newline=""), delimiter="\t"))
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    base_by_sid = {int(x["source_index"]): x for x in baseline["samples"]}
    if len(rows) != 24 or len(base_by_sid) != 24:
        raise RuntimeError(f"expected 24 clean sources, got {len(rows)} manifest/{len(base_by_sid)} baseline")
    samples: list[CleanSample] = []
    for row in rows:
        sid = int(row["source_index"])
        ci = int(row["class_index"])
        if sid != ci + 1 or row["class_name"] != LABELS[ci]:
            raise RuntimeError(f"class identity mismatch at source {sid}")
        tensor = asset_root / "replay_out" / "layers" / f"{sid}.orig.tensor.bin"
        if tensor.stat().st_size != 2 * 1024 * 4:
            raise RuntimeError(f"bad tensor byte size: {tensor}")
        digest = sha256_file(tensor)
        if digest != row["model_input_sha256"]:
            raise RuntimeError(f"clean tensor SHA mismatch at source {sid}")
        iq = np.fromfile(tensor, dtype="<f4").reshape(2, 1024)
        if not np.isfinite(iq).all():
            raise RuntimeError(f"non-finite clean tensor at source {sid}")
        b = base_by_sid[sid]
        if b["manifest_model_input_sha256"] != digest:
            raise RuntimeError(f"baseline identity mismatch at source {sid}")
        samples.append(CleanSample(
            source_index=sid,
            class_index=ci,
            class_name=row["class_name"],
            seed=int(row["seed"]),
            source_sha256=digest,
            source=(iq[0] + 1j * iq[1]).astype(np.complex64),
            digital_pred=int(b["orig_pred"]),
            digital_correct=bool(b["orig_correct"]),
        ))
    samples.sort(key=lambda x: x.source_index)
    return samples


def build_frame(sample: CleanSample, train: np.ndarray, tail: np.ndarray) -> tuple[np.ndarray, float]:
    frame = np.concatenate((
        np.zeros(2048, dtype=np.complex64),
        train,
        np.tile(sample.source, 8),
        tail,
        np.zeros(2048, dtype=np.complex64),
    )).astype(np.complex64, copy=False)
    if frame.shape != (FRAME_COMPLEX,):
        raise RuntimeError(f"bad frame length {frame.shape}")
    peak = float(max(np.max(np.abs(frame.real)), np.max(np.abs(frame.imag))))
    scale = min(FIXED_SCALE, PEAK_LIMIT / max(peak, 1e-12))
    return frame, scale
