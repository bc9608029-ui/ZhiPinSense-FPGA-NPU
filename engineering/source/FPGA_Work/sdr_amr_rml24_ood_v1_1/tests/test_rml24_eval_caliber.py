"""Regression for the RML24 pilot selection-metric caliber bug.

The split index arrays are concatenated in sorted ``(label, snr)`` order, so the
old ``_build_eval_dataset`` prefix truncation made the trial-end ``rated_0_20`` a
single-class (OOK-only) subset while the epoch-log metric used the full 24-class
validation split.  This test locks in the fix: a bounded eval budget must be
*stratified* across (class, SNR) strata, and ``samples=None`` means the full split.
"""

from __future__ import annotations

import numpy as np

from evaluation.evaluate_rml24 import _stratified_indices

_STRATUM = 819          # int(4096 * 0.2) validation samples per (class, SNR)
_SNR_VALUES = np.arange(-20, 31, 2, dtype=np.float32)  # 26 strata


def _validation_layout() -> tuple[np.ndarray, np.ndarray]:
    """Reproduce the label-major / snr-minor ordering of the frozen split index."""
    labels: list[np.ndarray] = []
    snrs: list[np.ndarray] = []
    for label in range(24):
        for snr in _SNR_VALUES:
            labels.append(np.full(_STRATUM, label, dtype=np.int64))
            snrs.append(np.full(_STRATUM, float(snr), dtype=np.float32))
    return np.concatenate(labels), np.concatenate(snrs)


def test_prefix_was_ook_only_documents_the_bug():
    labels, snrs = _validation_layout()
    # 16384 = 20 strata of OOK (class 0): the old prefix was single-class.
    prefix = labels[:16384]
    assert set(np.unique(prefix)) == {0}
    assert len(prefix) == 16384


def test_stratified_subset_covers_all_classes_and_snrs():
    labels, snrs = _validation_layout()
    indices = _stratified_indices(labels, snrs, 16384, seed=2026)
    assert len(indices) == 16384
    assert indices == sorted(indices)
    assert len(set(indices)) == len(indices)  # no duplicate positions
    picked_labels = labels[indices]
    picked_snrs = snrs[indices]
    assert set(np.unique(picked_labels)) == set(range(24))  # all 24 classes
    assert set(np.unique(picked_snrs)) == set(_SNR_VALUES.tolist())  # all 26 SNR strata
    # Each class is represented roughly proportionally (16384 / 24 ~= 682).
    per_class = np.bincount(picked_labels, minlength=24)
    assert per_class.min() >= 500
    assert per_class.max() <= 900


def test_stratified_subset_preserves_snr_distribution_for_rated_slice():
    labels, snrs = _validation_layout()
    indices = _stratified_indices(labels, snrs, 16384, seed=7)
    picked_snrs = snrs[indices]
    rated = picked_snrs[(picked_snrs >= 0.0) & (picked_snrs <= 20.0)]
    # The 0..20 dB slice stays populated across all classes (the metric is 24-class).
    assert len(rated) > 0
    rated_labels = labels[indices][(picked_snrs >= 0.0) & (picked_snrs <= 20.0)]
    assert set(np.unique(rated_labels)) == set(range(24))


def test_stratified_subset_is_deterministic():
    labels, snrs = _validation_layout()
    a = _stratified_indices(labels, snrs, 16384, seed=42)
    b = _stratified_indices(labels, snrs, 16384, seed=42)
    assert a == b


def test_stratified_limit_at_or_above_full_returns_everything():
    labels, snrs = _validation_layout()
    n = len(labels)
    assert _stratified_indices(labels, snrs, n, seed=1) == list(range(n))
    assert _stratified_indices(labels, snrs, n + 100, seed=1) == list(range(n))
