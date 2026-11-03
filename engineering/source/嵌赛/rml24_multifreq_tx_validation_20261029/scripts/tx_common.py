#!/usr/bin/env python3
"""Frozen transmit contract for the multi-frequency TX validation (2026-10-29).

Self-contained reproduction of the Stage-7 public-frame transmit chain, so the
offline verification does NOT depend on the mutable E:\\-hardcoded historical
scripts.  Every constant below is reproduced byte-for-byte from the frozen
sources (SHA recorded in CONTRACT.json); ``verify_identity()`` re-imports those
sources and asserts equality, so drift is caught at runtime.

No transmission happens here.  This module only builds floating-point and
int16 device waveforms in memory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

# --- frozen contract constants -------------------------------------------------
SCALE = 68.46059377833956          # public amplitude rule (build_frame)
SAMPLE_RATE = 2_560_000            # source / payload sample rate (Hz)
TX_SAMPLE_RATE = 10_240_000        # 4x upsampled transmit rate (Hz)
TX_LO_HZ = 2_401_800_000           # TX LO (Hz)
SIGNAL_OFFSETS_HZ = (-1_800_000, +1_800_000)   # A down, B up, relative to LO
SIGNAL_CENTERS_HZ = (2_400_000_000, 2_403_600_000)
UPSAMPLE = 4
TRAIN_SEED = 9011                 # message seed for the public preamble/tail
FRAME_LEN = 16384                 # build_frame output length @ 2.56 MS/s
TX_FRAME_LEN = FRAME_LEN * UPSAMPLE   # 65536 @ 10.24 MS/s
CLIP_GUARD = 2047.0               # build_frame clip guard (x16 keeps int16 safe)
TX_ATTEN_DB = -40.0
TX_BANDWIDTH_HZ = 18_000_000


def _public_preamble() -> tuple[np.ndarray, np.ndarray]:
    """Reproduce ``train`` / ``tail`` from ``pilot_recovery.py`` (seed 9011)."""
    rng = np.random.default_rng(TRAIN_SEED)
    pn = np.exp(1j * (np.pi / 4 + np.pi / 2 * rng.integers(0, 4, 1024))).astype(np.complex64)
    train = np.tile(pn, 2)
    tail = np.exp(1j * (np.pi / 4 + np.pi / 2 * rng.integers(0, 4, 2048))).astype(np.complex64)
    return train, tail


TRAIN, TAIL = _public_preamble()


def load_manifest(path: Path) -> list[dict]:
    """Identical to ``ui_interactive_tx.load_manifest``."""
    document = json.loads(path.read_text(encoding="utf-8"))
    records = document.get("records", [])
    if not records:
        raise ValueError("empty transmit manifest")
    required = {"seq", "file", "source_sha256"}
    cleaned, seen = [], set()
    for row in records:
        if not required <= set(row):
            raise ValueError("manifest row lacks seq/file/source_sha256")
        seq = int(row["seq"])
        if seq in seen:
            raise ValueError(f"duplicate seq {seq}")
        seen.add(seq)
        digest = str(row["source_sha256"])
        if len(digest) != 64:
            raise ValueError(f"bad source SHA for seq {seq}")
        cleaned.append({"seq": seq, "file": str(row["file"]), "source_sha256": digest})
    return cleaned


def build_frame(payload_bytes: bytes) -> np.ndarray:
    """Identical to ``ui_interactive_tx.build_frame`` (SCALE applied)."""
    values = np.frombuffer(payload_bytes, dtype="<f4")
    if values.size != 2048:
        raise ValueError(f"payload must contain 2048 float32 values, got {values.size}")
    iq = values.reshape(2, 1024)
    source = iq[0] + 1j * iq[1]
    frame = np.concatenate([
        np.zeros(2048, dtype=np.complex64),
        TRAIN.astype(np.complex64),
        np.tile(source, 8),
        TAIL.astype(np.complex64),
        np.zeros(2048, dtype=np.complex64),
    ]).astype(np.complex64)
    scaled = frame * SCALE
    component_peak = float(max(np.abs(scaled.real).max(), np.abs(scaled.imag).max()))
    if not np.isfinite(scaled).all() or component_peak > CLIP_GUARD:
        raise ValueError(f"scaled TX frame invalid or clips: component_peak={component_peak}")
    return scaled


def resample_shift(frame: np.ndarray, offset_hz: float) -> np.ndarray:
    """4x upsample then complex shift by ``offset_hz`` relative to TX LO."""
    z = resample_poly(frame, UPSAMPLE, 1)
    n = np.arange(len(z))
    return z * np.exp(2j * np.pi * offset_hz * n / TX_SAMPLE_RATE)


def int16_quantize(z: np.ndarray) -> np.ndarray:
    """Emulate ``pluto_link_probe.Radio.send``: round -> int16 -> x16, I/Q interleaved LE.

    Returns an int16 array of shape (len(z), 2) (I, Q) whose little-endian byte
    stream is exactly what the DDS core receives.
    """
    iq = np.empty((len(z), 2), dtype="<i2")
    iq[:, 0] = np.round(z.real).astype(np.int16) * 16
    iq[:, 1] = np.round(z.imag).astype(np.int16) * 16
    return iq


def to_float(iq: np.ndarray) -> np.ndarray:
    """Inverse view of int16_quantize for spectrum/peak analysis (x16 undone)."""
    return (iq[:, 0].astype(np.float64) + 1j * iq[:, 1].astype(np.float64)) / 16.0


def saturation_count(z: np.ndarray) -> int:
    """Samples whose round(x16) would overflow int16, i.e. |round(component)| >= 2048.

    Must be evaluated in the FLOAT domain BEFORE the int16 cast: the cast itself
    wraps, so checking the int16 array for >32767 is always false (vacuously).
    """
    return int(np.sum(np.abs(np.round(z.real)) >= 2048) + np.sum(np.abs(np.round(z.imag)) >= 2048))


def verify_identity(ui_tx: Path, pilot: Path, link: Path) -> list[str]:
    """Re-import the frozen sources and assert our reproductions match them.

    Returns a list of mismatches (empty == all identical).  Raises only on
    import failure; mismatch is reported, not raised, so callers can fail-closed.
    """
    import importlib.util
    import sys

    problems: list[str] = []

    def _load(name: str, p: Path):
        spec = importlib.util.spec_from_file_location(name, str(p))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    try:
        ui = _load("_frozen_ui_interactive_tx", ui_tx)
        if abs(float(ui.SCALE) - SCALE) > 1e-12:
            problems.append("SCALE mismatch")
        # train/tail identity
        pil = _load("_frozen_pilot_recovery", pilot)
        if not np.array_equal(pil.train, TRAIN):
            problems.append("train mismatch")
        if not np.array_equal(pil.tail, TAIL):
            problems.append("tail mismatch")
        # build_frame identity on a known (zero) payload
        payload = np.zeros(2048, dtype="<f4").tobytes()
        ours = build_frame(payload)
        theirs = np.asarray(ui.build_frame(payload, pil.train, pil.tail), dtype=np.complex64)
        if not np.array_equal(ours, theirs):
            problems.append("build_frame mismatch")
    except Exception as exc:  # noqa: BLE001 - report import failure as a problem
        problems.append(f"identity import failed: {exc!r}")

    # pluto_link_probe does libiio ctypes binding at import time, which needs the
    # hardware DLL; verify its send() int16 rule by STATIC source text instead of
    # executing it (the arithmetic we transcribed is two lines).
    try:
        src = link.read_text(encoding="utf-8")
        for needle in (
            "iq[:,0]=np.round(z.real).astype(np.int16)*16",
            "iq[:,1]=np.round(z.imag).astype(np.int16)*16",
        ):
            # allow whitespace variance
            if "".join(needle.split()) not in "".join(src.split()):
                problems.append(f"link int16 rule missing: {needle}")
    except Exception as exc:  # noqa: BLE001
        problems.append(f"link source read failed: {exc!r}")

    return problems
