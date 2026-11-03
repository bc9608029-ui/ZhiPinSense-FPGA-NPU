"""M10: the OOD families are disjoint and generation is finite, RMS-normalized, planar."""

from __future__ import annotations

import numpy as np
import pytest

from datasets.ood_dataset import (
    OOD_FAMILIES,
    SPLIT_CODES,
    generate_ood_records,
    to_planar,
)


def test_families_are_pairwise_disjoint():
    names = list(OOD_FAMILIES)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert set(OOD_FAMILIES[a]).isdisjoint(set(OOD_FAMILIES[b])), (a, b)


def test_split_codes_are_distinct():
    assert set(SPLIT_CODES) == {"oe_aux_train", "ood_validation", "ood_final_test"}
    assert len(set(SPLIT_CODES.values())) == 3


@pytest.mark.parametrize("family", ["near_24", "far", "ambiguous"])
def test_generate_is_finite_and_unit_rms(family):
    records = generate_ood_records(family, "ood_final_test", seed=3407, count_per_modulation=1)
    assert records.iq.dtype == np.complex64
    assert records.iq.shape[0] == len(OOD_FAMILIES[family])
    assert records.iq.shape[1] == 1024
    assert np.isfinite(records.iq).all()
    magnitude = np.abs(records.iq.astype(np.complex128))
    rms = np.sqrt(np.mean(magnitude ** 2, axis=1))
    np.testing.assert_allclose(rms, 1.0, rtol=1e-3)


def test_planar_layout_matches_iq():
    records = generate_ood_records("far", "ood_final_test", seed=3407, count_per_modulation=1)
    planar = records.planar
    assert planar.shape == (len(records), 2, 1024)
    assert planar.dtype == np.float32
    np.testing.assert_allclose(planar[:, 0, :], records.iq.real.astype(np.float32), atol=1e-6)
    np.testing.assert_allclose(planar[:, 1, :], records.iq.imag.astype(np.float32), atol=1e-6)


def test_to_planar_standalone():
    iq = np.array([[1 + 2j, 3 + 4j]], dtype=np.complex64)
    planar = to_planar(iq)
    assert planar.shape == (1, 2, 2)
    np.testing.assert_allclose(planar[0, 0], [1.0, 3.0])
    np.testing.assert_allclose(planar[0, 1], [2.0, 4.0])


def test_unknown_family_split_and_zero_count_rejected():
    with pytest.raises(ValueError):
        generate_ood_records("nope", "ood_final_test", seed=0, count_per_modulation=1)
    with pytest.raises(ValueError):
        generate_ood_records("far", "nope", seed=0, count_per_modulation=1)
    with pytest.raises(ValueError):
        generate_ood_records("far", "ood_final_test", seed=0, count_per_modulation=0)
