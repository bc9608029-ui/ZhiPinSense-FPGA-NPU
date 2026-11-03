"""M20 test categories 10-12: split zero-overlap, premature-access reject,
generator-shortcut audit.
"""

from __future__ import annotations

import numpy as np
import pytest

from ood_u import contract
from ood_u.data import (
    SplitRecords,
    assert_no_overlap,
    generate_id_split,
    generate_ood_split,
    signal_config,
)
from ood_u.manifest import FinalTestGuard
from ood_u.shortcut import audit_shortcut, assert_shared_domain


def test_id_ood_split_zero_overlap():
    # Category 10: the real generated splits share no sample bytes.
    id_rec = generate_id_split("ood_validation", seed=contract.OOD_SEED, count_per_class=2)
    near_rec = generate_ood_split("near_12", "ood_validation", seed=contract.OOD_SEED, count_per_modulation=2)
    far_rec = generate_ood_split("far", "ood_validation", seed=contract.OOD_SEED, count_per_modulation=2)
    assert_no_overlap(id_rec, near_rec, far_rec)


def test_split_overlap_guard_raises():
    # A synthetic overlap across split/family must fail closed.
    cfg = signal_config()
    planar = np.zeros((1, 2, 1024), dtype=np.float32)
    hashes = ["a" * 64]
    a = SplitRecords(planar=planar, modulation=np.array(["OOK"], dtype=object),
                     snr_db=np.array([10.0]), family="id", split="ood_validation",
                     seed=0, signal_config=cfg, sample_hashes=hashes)
    b = SplitRecords(planar=planar, modulation=np.array(["OOK"], dtype=object),
                     snr_db=np.array([10.0]), family="id", split="ood_final_test",
                     seed=0, signal_config=cfg, sample_hashes=hashes)
    with pytest.raises(RuntimeError):
        assert_no_overlap(a, b)


def test_final_test_premature_access_reject(tmp_path):
    # Category 11: the final-test guard allows exactly one access, fail-closed.
    guard = FinalTestGuard(tmp_path / "access.json")
    guard.assert_not_accessed()          # first check passes
    guard.mark_accessed("run_id", "m" * 64)
    with pytest.raises(RuntimeError):
        guard.assert_not_accessed()       # second access forbidden
    with pytest.raises(RuntimeError):
        guard.mark_accessed("run_id2", "m" * 64)


def test_generator_shortcut_not_detected():
    # Category 12: no single cheap feature separates ID from OOD (shared domain).
    id_rec = generate_id_split("ood_validation", seed=contract.OOD_SEED, count_per_class=4)
    near_rec = generate_ood_split("near_12", "ood_validation", seed=contract.OOD_SEED, count_per_modulation=4)
    far_rec = generate_ood_split("far", "ood_validation", seed=contract.OOD_SEED, count_per_modulation=4)
    assert_shared_domain(id_rec, near_rec, far_rec)
    ood_planar = np.concatenate([near_rec.planar, far_rec.planar], axis=0)
    feature_auroc, shortcut = audit_shortcut(id_rec.planar, ood_planar)
    assert set(feature_auroc) == {"rms_power", "papr", "bandwidth_frac", "spectral_centroid"}
    assert not shortcut, feature_auroc
