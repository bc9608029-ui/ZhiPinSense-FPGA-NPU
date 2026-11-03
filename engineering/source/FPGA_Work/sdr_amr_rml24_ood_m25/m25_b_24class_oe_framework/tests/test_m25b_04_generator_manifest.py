"""Generator-manifest tests: record fields, stable SHA, write-once semantics."""
import json
import os

import numpy as np
import pytest

from datasets import m25b_generator_manifest as m


@pytest.fixture
def samples():
    return np.arange(2 * 2 * 1024, dtype=np.float32).reshape(2, 2, 1024)


def test_build_record_fields(samples):
    rec = m.build_record(modulation="LFM", source="far", family_code=5,
                         split_code=1, split_name="ood_validation", seed=2026,
                         count=2, sample_length=1024, sample_rate=200000.0,
                         amplitude_rms=1.0, samples=samples)
    for key in m.REQUIRED_FIELDS:
        assert key in rec
    assert rec["samples_sha256"] == m.samples_sha256(samples)


def test_sha256_stable(samples):
    assert m.samples_sha256(samples) == m.samples_sha256(np.ascontiguousarray(samples))


def test_write_once_idempotent(samples, tmp_path):
    path = str(tmp_path / "manifest.json")
    rec = m.build_record(modulation="LFM", source="far", family_code=5,
                         split_code=1, split_name="ood_validation", seed=2026,
                         count=2, sample_length=1024, sample_rate=200000.0,
                         amplitude_rms=1.0, samples=samples)
    m.write_once(path, rec)
    m.write_once(path, rec)  # identical -> no-op
    with open(path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert len(manifest) == 1


def test_write_once_refuses_different_sha(samples, tmp_path):
    path = str(tmp_path / "manifest.json")
    rec = m.build_record(modulation="LFM", source="far", family_code=5,
                         split_code=1, split_name="ood_validation", seed=2026,
                         count=2, sample_length=1024, sample_rate=200000.0,
                         amplitude_rms=1.0, samples=samples)
    m.write_once(path, rec)
    other = dict(rec)
    other["samples_sha256"] = "0" * 64
    with pytest.raises(RuntimeError):
        m.write_once(path, other)
