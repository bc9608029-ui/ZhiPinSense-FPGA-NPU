"""Fixed IQ parity set + host reference logits for the NPU logits parity check.

The parity set is a small deterministic set of known 12-class samples (at 0 and
10 dB) plus representative near_12 / far unknown samples, saved as raw fp32
planar [N, 2, 1024] so the board-side capture tool can feed the *exact* bytes
through the NPU.  Host reference logits (PyTorch fp32 + ONNX) are produced here;
the NPU column is captured on the board and compared by ``compare_logits``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from channel.awgn import add_awgn
from datasets.modulation_generator import generate_iq
from datasets.ood_generator import generate_ood_iq
from ood_u import contract
from ood_u.data import signal_config, _to_planar
from ood_u.model import ADAMRV11Net, predict_logits, predict_logits_onnx

_PARITY_SEED = contract.OOD_SEED + 77


def build_parity_iq() -> tuple[np.ndarray, list[str]]:
    """Return (planar [N,2,1024] fp32, per-sample label) for the parity set."""
    cfg = signal_config()
    planar_list: list[np.ndarray] = []
    labels: list[str] = []

    def add_known(mod: str, snr: float, idx: int) -> None:
        rng = np.random.default_rng(np.random.SeedSequence([_PARITY_SEED, 1, idx]))
        iq, _ = generate_iq(mod, cfg, rng)
        iq, _ = add_awgn(iq, snr, rng)
        planar_list.append(_to_planar(iq))
        labels.append(f"id:{mod}@{snr:g}dB")

    def add_ood(mod: str, family: str, snr: float, idx: int) -> None:
        rng = np.random.default_rng(np.random.SeedSequence([_PARITY_SEED, 2, idx]))
        iq, _ = generate_ood_iq(mod, cfg, rng)
        iq, _ = add_awgn(iq, snr, rng)
        planar_list.append(_to_planar(iq))
        labels.append(f"ood:{family}:{mod}@{snr:g}dB")

    idx = 0
    for snr in (0.0, 10.0):
        for mod in contract.LABEL_ORDER_12:
            add_known(mod, snr, idx)
            idx += 1
    for mod in ("8ASK", "16PSK", "32QAM", "OQPSK"):      # near_12 representatives
        add_ood(mod, "near_12", 10.0, idx)
        idx += 1
    for mod in ("LFM", "CW", "MULTITONE"):               # far representatives
        add_ood(mod, "far", 10.0, idx)
        idx += 1

    planar = np.stack(planar_list).astype(np.float32)
    return planar, labels


def _write_raw(planar: np.ndarray, path: Path) -> str:
    data = np.ascontiguousarray(planar, dtype=np.float32)
    path.write_bytes(data.tobytes())
    return hashlib.sha256(data.tobytes()).hexdigest()


def save_reference_bundle(
    out_dir: Path,
    planar: np.ndarray,
    labels: list[str],
    model: ADAMRV11Net,
    onnx_path: Path,
) -> dict[str, Any]:
    """Write the raw IQ set, metadata, and host reference logits; return the manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    iq_sha = _write_raw(planar, out_dir / "parity_iq.bin")

    pt_logits = predict_logits(model, planar)
    onnx_logits = predict_logits_onnx(onnx_path, planar)

    meta: dict[str, Any] = {
        "n": int(planar.shape[0]),
        "shape": list(planar.shape),
        "dtype": "float32",
        "layout": "planar_iq_c_order",
        "sample_length": contract.SAMPLE_LENGTH,
        "labels": labels,
        "parity_seed": _PARITY_SEED,
        "iq_sha256": iq_sha,
    }
    (out_dir / "parity_iq_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def _dump(name: str, logits: np.ndarray) -> dict[str, Any]:
        payload = {
            "n": int(logits.shape[0]),
            "output_dim": int(logits.shape[1]),
            "logits": logits.tolist(),
        }
        (out_dir / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    _dump("reference_pytorch_logits.json", pt_logits)
    _dump("reference_onnx_logits.json", onnx_logits)
    return meta


__all__ = ["build_parity_iq", "save_reference_bundle", "_PARITY_SEED"]
