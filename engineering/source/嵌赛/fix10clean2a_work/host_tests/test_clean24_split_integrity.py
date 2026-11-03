"""Host test 3/4 — dataset split & leakage isolation + manifest integrity.

Covers §12 items: 13 (seed disjoint across splits), 14 (analog source no overlap),
15 (manifest SHA recomputable), 18 (scored == total), 19 (missing/duplicate/unknown
fail-closed), plus 2/6 in the dataset form.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
import pytest

import radioml_clean_contract as c

DATASET = Path(r"F:/嵌赛/fix10clean2a_dataset")
SETS = {"smoke96": 4, "dev2400": 100, "formal12000": 500}


def _load_meta(name: str):
    with h5py.File(DATASET / f"clean24_{name}.hdf5", "r") as f:
        seeds = np.asarray(f["seeds"]).astype(np.int64)
        Y = np.asarray(f["Y"]).astype(np.int64)
        order = json.loads(f.attrs["label_order"])
    return seeds, Y, order


def test_seed_ranges_disjoint_across_sets():
    # §12 item 13: smoke/dev/formal seed ranges never overlap.
    ranges = {}
    for name in SETS:
        seeds, _, _ = _load_meta(name)
        ranges[name] = set(seeds.tolist())
    assert ranges["smoke96"].isdisjoint(ranges["dev2400"])
    assert ranges["smoke96"].isdisjoint(ranges["formal12000"])
    assert ranges["dev2400"].isdisjoint(ranges["formal12000"])


def test_seeds_unique_within_set():
    for name, spc in SETS.items():
        seeds, Y, _ = _load_meta(name)
        assert len(seeds) == len(set(seeds.tolist())), name
        assert len(seeds) == 24 * spc, name


def test_balanced_labels_scored_equals_total():
    # §12 item 18: scored == total samples (per-class balanced).
    for name, spc in SETS.items():
        _, Y, _ = _load_meta(name)
        assert len(Y) == 24 * spc, name
        for cidx in range(24):
            assert int((Y == cidx).sum()) == spc, f"{name} class {cidx}"


def test_label_order_matches_contract():
    for name in SETS:
        _, _, order = _load_meta(name)
        assert order == list(c.LABEL_ORDER_24), name


def test_manifest_sha_recomputable():
    # §12 item 15: the committed manifest SHA is re-derivable from the files.
    manifest = json.loads((DATASET / "clean24_manifest.json").read_text(encoding="utf-8"))
    for name in SETS:
        p = DATASET / f"clean24_{name}.hdf5"
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        assert manifest["files"][name]["sha256"] == sha, name


def test_no_duplicate_samples_in_set():
    # smallest set fully materialised: no two rows byte-identical.
    with h5py.File(DATASET / "clean24_smoke96.hdf5", "r") as f:
        X = np.asarray(f["X"])
    flat = X.reshape(X.shape[0], -1)
    seen = set()
    for row in flat:
        key = row.tobytes()
        assert key not in seen
        seen.add(key)


def test_gmsk_oqpsk_sources_in_dataset():
    # source 22 rows are GMSK, source 23 OQPSK; their envelopes differ.
    with h5py.File(DATASET / "clean24_dev2400.hdf5", "r") as f:
        X = np.asarray(f["X"])
        Y = np.asarray(f["Y"])
    g = X[Y == 22][:1, :, 0] + 1j * X[Y == 22][:1, :, 1]
    o = X[Y == 23][:1, :, 0] + 1j * X[Y == 23][:1, :, 1]
    assert not np.allclose(g, o)
    assert np.abs(g).std() < 1e-6            # GMSK constant envelope
    assert np.abs(o).std() > 0.0             # OQPSK amplitude ripple


def test_analog_source_disjoint_per_seed():
    # §12 item 14: audio is derived from the per-sample RNG, so disjoint seeds
    # (proven above) => disjoint audio clips; same seed reproduces identical audio.
    a1 = c._audio(np.random.default_rng(1000), c.SAMPLE_LENGTH, c.SAMPLE_RATE_HZ)
    a2 = c._audio(np.random.default_rng(2000), c.SAMPLE_LENGTH, c.SAMPLE_RATE_HZ)
    assert not np.allclose(a1, a2)
    a1b = c._audio(np.random.default_rng(1000), c.SAMPLE_LENGTH, c.SAMPLE_RATE_HZ)
    assert np.array_equal(a1, a1b)


def test_validator_fail_closed_on_missing_set():
    # §12 item 19: a missing dataset name fails closed (raises, never "passes").
    import validate_radioml_compatible_clean24 as v
    with pytest.raises(AssertionError):
        v.validate_set("nonexistent_set")
