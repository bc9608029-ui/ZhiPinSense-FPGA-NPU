"""Generator-shortcut audit for the 12-class OOD-U data.

ID and OOD samples must live in the same data domain.  This module extracts the
cheap, model-free scalar features a classifier could trivially exploit — RMS
power, PAPR, occupied-bandwidth fraction, spectral centroid — and checks whether
any single feature separates ID from OOD with high AUROC.  If one does, the
protocol is declared invalid (``generator_shortcut``).

The sample rate is a config constant shared by both ID and OOD (asserted here),
so it can never be a per-sample shortcut.
"""

from __future__ import annotations

import numpy as np

from ood.metrics import auroc
from ood_u import contract

# A single cheap feature that reaches this AUROC (either direction) is a shortcut.
AUROC_SHORTCUT_THRESHOLD = 0.90


def _complex_iq(planar: np.ndarray) -> np.ndarray:
    arr = np.asarray(planar, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[1] != 2:
        raise ValueError(f"expected planar IQ [N,2,L], got {arr.shape}")
    return arr[:, 0] + 1j * arr[:, 1]


def simple_features(planar: np.ndarray) -> dict[str, np.ndarray]:
    """Model-free scalar features (one value per sample)."""
    iq = _complex_iq(planar)
    power = np.mean(np.abs(iq) ** 2, axis=1)
    peak = np.max(np.abs(iq) ** 2, axis=1)
    papr = peak / np.maximum(power, np.finfo(np.float64).tiny)

    spectrum = np.abs(np.fft.fftshift(np.fft.fft(iq, axis=1), axes=1)) ** 2
    total = spectrum.sum(axis=1)
    length = spectrum.shape[1]
    lo, hi = length // 4, (3 * length) // 4
    bandwidth_frac = spectrum[:, lo:hi].sum(axis=1) / np.maximum(total, np.finfo(np.float64).tiny)

    freqs = np.arange(length, dtype=np.float64)
    spectral_centroid = (spectrum * freqs).sum(axis=1) / np.maximum(total, np.finfo(np.float64).tiny) / length

    return {
        "rms_power": power,
        "papr": papr,
        "bandwidth_frac": bandwidth_frac,
        "spectral_centroid": spectral_centroid,
    }


def audit_shortcut(
    id_planar: np.ndarray,
    ood_planar: np.ndarray,
    *,
    auroc_threshold: float = AUROC_SHORTCUT_THRESHOLD,
) -> tuple[dict[str, float], bool]:
    """Return per-feature AUROC and whether a generator shortcut was detected.

    ``shortcut_detected`` is True when any single feature separates ID from OOD
    with |AUROC - 0.5| >= (auroc_threshold - 0.5).
    """
    id_feats = simple_features(id_planar)
    ood_feats = simple_features(ood_planar)
    if set(id_feats) != set(ood_feats):
        raise RuntimeError("ID/OOD feature sets diverged; generation is inconsistent")

    report: dict[str, float] = {}
    shortcut = False
    for name in id_feats:
        value = float(auroc(id_feats[name], ood_feats[name]))
        report[name] = value
        if abs(value - 0.5) >= (auroc_threshold - 0.5):
            shortcut = True
    return report, shortcut


def assert_shared_domain(*records: object) -> None:
    """Fail-closed: every record set must share the same signal domain config."""
    import json

    configs = {json.dumps(getattr(r, "signal_config", {}), sort_keys=True) for r in records}
    if len(configs) != 1:
        raise RuntimeError(
            "ID/OOD signal domains differ (sample rate / length / amplitude mismatch) — "
            "generator shortcut risk; refusing to proceed"
        )


__all__ = ["simple_features", "audit_shortcut", "assert_shared_domain", "AUROC_SHORTCUT_THRESHOLD"]
