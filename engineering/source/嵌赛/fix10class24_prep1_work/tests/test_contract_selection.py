"""fix10class24-prep1: fixed-selection + fail-closed input rejection tests."""

import json
import os
import sys

import h5py
import numpy as np
import pytest

sys.dont_write_bytecode = True

PRED_HEADER = ("sample_id\traw24_label\tdeployed23_label\traw24_pred\t"
               "deployed23_pred\ttop1_logit\ttop2_logit\tmargin\t"
               "correct_raw24\tcorrect_deployed23")


def _pred_tsv_text(B, drop_sids=()):
    """A structurally valid 10-column predictions TSV derived from the contract
    (raw24_pred == raw24_label, deployed23_pred == deployed23_label, both
    correct) -- used as a synthetic input for the fail-closed rejection tests."""
    lines = [PRED_HEADER]
    for s in B.fixed_samples():
        if s["source_index"] in drop_sids:
            continue
        dep = B.DEPLOYED_LABEL_ORDER_23[s["deployed23_class"]]
        lines.append("\t".join([
            str(s["source_index"]), s["raw24_label"], dep,
            s["raw24_label"], dep, "5.0", "1.0", "4.0", "1", "1"]))
    return "\n".join(lines) + "\n"


def test_fixed_24_source_indices(build_mod):
    B = build_mod
    samples = B.fixed_samples()
    assert len(samples) == 24
    for s in samples:
        assert s["source_index"] == s["class_index"] * B.SPC
        assert s["seed"] == B.SEED_BASE + s["source_index"]  # k == 0
        assert s["raw24_label"] == B.SOURCE_LABEL_ORDER_24[s["class_index"]]
        assert s["deployed23_class"] == int(B.SOURCE_TO_DEPLOYED[s["class_index"]])
    assert [s["source_index"] for s in samples] == [ci * 500 for ci in range(24)]
    assert samples[0]["raw24_label"] == "OOK" and samples[0]["source_index"] == 0
    assert samples[23]["raw24_label"] == "OQPSK" and samples[23]["source_index"] == 11500
    slugs = [B.slug(s["raw24_label"]) for s in samples]
    assert len(set(slugs)) == 24  # collision-free filenames


def test_predictions_tsv_duplicate_sample_rejected(build_mod, tmp_work):
    B = build_mod
    p = os.path.join(tmp_work, "dup.tsv")
    lines = _pred_tsv_text(B).splitlines()
    lines.insert(2, lines[1])  # duplicate the first data row (sample_id 0)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    with pytest.raises(SystemExit, match="duplicate sample_id"):
        B.load_predictions(p)


def test_predictions_tsv_missing_sample_rejected(build_mod, tmp_work, monkeypatch):
    B = build_mod
    p = os.path.join(tmp_work, "missing0.tsv")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(_pred_tsv_text(B, drop_sids={0}))
    monkeypatch.setattr(B, "PRED_TSV_PATH", p)
    monkeypatch.setattr(B, "EXPECTED_PRED_SHA", B.sha256_file(p))
    with pytest.raises(SystemExit, match="missing from predictions TSV"):
        B.build_artifacts(os.path.join(tmp_work, "out"))


def test_predictions_tsv_bad_header_rejected(build_mod, tmp_work):
    B = build_mod
    p = os.path.join(tmp_work, "badhdr.tsv")
    with open(p, "w", encoding="utf-8") as f:
        f.write("wrong\theader\there\n")
    with pytest.raises(AssertionError):
        B.load_predictions(p)


def test_class_order_misalignment_rejected(build_mod, monkeypatch):
    B = build_mod
    perm = list(B.SOURCE_LABEL_ORDER_24)
    perm[0], perm[1] = perm[1], perm[0]
    monkeypatch.setattr(B, "SOURCE_LABEL_ORDER_24", perm)
    with pytest.raises(SystemExit, match="label_order mismatch"):
        B.read_hdf5()


def _write_synthetic_hdf5(path, shape, dtype, label_order):
    with h5py.File(path, "w") as f:
        f.create_dataset("X", data=np.zeros(shape, dtype=dtype))
        f.create_dataset("Y", data=np.zeros(shape[0], dtype=np.int64))
        f.create_dataset("seeds", data=np.zeros(shape[0], dtype=np.int64))
        f.attrs["label_order"] = json.dumps(label_order)
        f.attrs["seed_base"] = 2000000
        f.attrs["samples_per_class"] = 500


def test_hdf5_wrong_shape_rejected(build_mod, tmp_work, monkeypatch):
    B = build_mod
    p = os.path.join(tmp_work, "bad_shape.hdf5")
    _write_synthetic_hdf5(p, (5, 1024, 2), np.float32, list(B.SOURCE_LABEL_ORDER_24))
    monkeypatch.setattr(B, "DATASET_PATH", p)
    with pytest.raises(SystemExit, match="unexpected X shape/dtype"):
        B.read_hdf5()


def test_hdf5_wrong_dtype_rejected(build_mod, tmp_work, monkeypatch):
    B = build_mod
    p = os.path.join(tmp_work, "bad_dtype.hdf5")
    _write_synthetic_hdf5(p, (5, 1024, 2), np.float64, list(B.SOURCE_LABEL_ORDER_24))
    monkeypatch.setattr(B, "DATASET_PATH", p)
    with pytest.raises(SystemExit, match="unexpected X shape/dtype"):
        B.read_hdf5()
