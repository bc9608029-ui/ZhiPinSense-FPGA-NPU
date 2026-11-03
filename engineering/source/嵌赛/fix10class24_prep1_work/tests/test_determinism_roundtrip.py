"""fix10class24-prep1: determinism, wrong-SHA/length rejection, roundtrip."""

import json
import os
import sys

import numpy as np
import pytest

sys.dont_write_bytecode = True


def test_sha256_file_deterministic_and_tamper_sensitive(build_mod, work_smoke, tmp_work):
    B = build_mod
    p = os.path.join(work_smoke, "source_ook.f32")
    assert B.sha256_file(p) == B.sha256_file(p)   # same input -> same digest
    assert len(B.sha256_file(p)) == 64
    b = open(p, "rb").read()
    tampered = os.path.join(tmp_work, "tamper.f32")
    ba = bytearray(b)
    ba[0] ^= 0xFF
    open(tampered, "wb").write(bytes(ba))
    assert B.sha256_file(tampered) != B.sha256_file(p)   # wrong-SHA basis


def test_read_tensor_f32_wrong_length_rejected(verify_mod, tmp_work):
    V = verify_mod
    p = os.path.join(tmp_work, "short.f32")
    np.zeros(100, dtype="<f4").tofile(p)
    with pytest.raises(SystemExit, match="want 2048"):
        V.read_tensor_f32(p)


def test_build_two_run_consistent(build_mod, tmp_work):
    B = build_mod
    sha1, meta1 = B.build_artifacts(os.path.join(tmp_work, "run1"))
    sha2, meta2 = B.build_artifacts(os.path.join(tmp_work, "run2"))
    assert sha1 == sha2
    assert json.dumps(meta1, sort_keys=True) == json.dumps(meta2, sort_keys=True)
    for sha in (sha1, sha2):
        nb = sum(1 for n in sha if n.endswith(".ci16") or n.endswith(".f32"))
        nt = sum(1 for n in sha if n.endswith(".tsv"))
        assert nb == 72 and nt == 6


def test_roundtrip_24_of_24(verify_mod, work_smoke, tmp_work, monkeypatch):
    V = verify_mod
    out = os.path.join(tmp_work, "results")
    monkeypatch.setattr(sys, "argv", [
        "verify_clean24_smoke_roundtrip.py",
        "--smoke-dir", work_smoke, "--out-dir", out])
    rc = V.main()
    assert rc == 0
    rep = json.load(open(os.path.join(out,
                                      "clean24_smoke_roundtrip_report.json"),
                         encoding="utf-8"))
    assert rep["acceptance_pass"] is True
    assert rep["n_samples"] == 24
    assert rep["raw24_prediction_agreement"] == "24/24"
    assert rep["deployed23_prediction_agreement"] == "24/24"
    assert rep["raw24_label_correct"] == "24/24"
    assert rep["deployed23_label_correct"] == "24/24"
    assert rep["clip_count_zero"] == "24/24"
    assert rep["nan_inf_total"] == 0
    assert rep["raw24_class_coverage"] == "24/24"
    assert rep["deployed23_class_coverage"] == "23/23"
    # AM-SSB double-merge cross-check on the roundtrip itself
    amssb = [s for s in rep["samples"]
             if s["true_deployed23_label"] == "AM-SSB"]
    assert len(amssb) == 2
    assert {s["modulation"] for s in amssb} == {"AM-SSB-WC", "AM-SSB-SC"}
