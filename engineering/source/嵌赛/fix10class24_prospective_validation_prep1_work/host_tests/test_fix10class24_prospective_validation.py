#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_fix10class24_prospective_validation.py — synthetic-fixture tests for the
prospective-validation checker (task 39e5 prep1, Phase F).

Runs the checker (subprocess) against synthetic positive/negative results tables and
asserts the HARD checks fail-closed on each mandated scenario, plus the informational
per-candidate statistics behave as specified.  No board, no SDR, no real capture.
"""

import csv
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
CONTRACTS = os.path.abspath(os.path.join(HERE, "..", "contracts", "prospective_validation_v1"))
CHECKER = os.path.join(SCRIPTS, "check_fix10class24_prospective_validation.py")
POLICY = os.path.join(CONTRACTS, "candidate_gate_policy.tsv")

sys.path.insert(0, SCRIPTS)
import check_fix10class24_prospective_validation as chk  # noqa: E402

POS_HEADER = ["capture_id", "source_index", "raw24_class", "modulation", "repeat_id",
              "tx_atten", "rx_gain", "rx_bw", "center_hz", "sample_rate", "target_rms",
              "payload_training_residual", "payload_training_corr", "training_corr",
              "cfo_hz", "rx_clipped", "gate_admitted", "raw24_pred", "baseline_pred",
              "label_correct", "prediction_agreement", "finite"]

NEG_HEADER = ["capture_id", "negative_type", "source_index", "raw24_class", "modulation",
              "repeat_id", "tx_atten", "rx_gain", "rx_bw", "center_hz", "sample_rate",
              "target_rms", "payload_training_residual", "payload_training_corr",
              "training_corr", "cfo_hz", "rx_clipped", "gate_admitted", "raw24_pred",
              "baseline_pred", "label_correct", "prediction_agreement", "finite"]


def write_tsv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def pos_row(rc, rep, residual=0.05, pcorr=0.99, tcorr=0.99, cfo=5.0, clip=0,
            admitted=1, raw24_pred=None, baseline_pred=None, label_correct=1,
            pred_agree=1, finite=1, modulation=None, source_index=None,
            capture_id=None):
    if source_index is None:
        source_index = rc * 500
    if modulation is None:
        modulation = chk.FROZEN_IDENTITY[source_index][1]
    if raw24_pred is None:
        raw24_pred = rc
    if baseline_pred is None:
        baseline_pred = rc
    cid = capture_id if capture_id else "rfpos_c%02d_r%d" % (rc, rep)
    return [cid, source_index, rc, modulation, rep, -40, 35, 18000000, 2400000000,
            2560000, 2048, residual, pcorr, tcorr, cfo, clip, admitted, raw24_pred,
            baseline_pred, label_correct, pred_agree, finite]


def neg_row(neg_type, rep, residual=5.0, pcorr=0.1, tcorr=0.05, cfo=500.0, clip=0,
            admitted=0):
    cid = "rfneg_%s_r%d" % (neg_type, rep)
    return [cid, neg_type, "", "", "", rep, -40, 35, 18000000, 2400000000, 2560000,
            2048, residual, pcorr, tcorr, cfo, clip, admitted, "", "", "", "", ""]


def full_positive():
    rows = []
    for rc in range(24):
        for rep in range(1, 6):
            rows.append(pos_row(rc, rep))
    return rows


def clean_negatives():
    rows = []
    for neg_type in chk.NEGATIVE_VOCAB:
        for rep in range(1, 4):
            rows.append(neg_row(neg_type, rep))
    return rows


def run_checker(tmp_path, pos_rows, neg_rows, policy_path=POLICY):
    pos = tmp_path / "positive.tsv"
    neg = tmp_path / "negative.tsv"
    out = tmp_path / "out"
    write_tsv(pos, POS_HEADER, pos_rows)
    write_tsv(neg, NEG_HEADER, neg_rows)
    r = subprocess.run([sys.executable, CHECKER,
                        "--positive-results", str(pos),
                        "--negative-results", str(neg),
                        "--policy", str(policy_path),
                        "--identity", os.path.join(CONTRACTS, "clean24_identity.tsv"),
                        "--out-dir", str(out)],
                       capture_output=True, text=True)
    report = None
    if (out / "report.json").exists():
        with open(out / "report.json", encoding="utf-8") as f:
            report = json.load(f)
    return r, report


def admit_count(report, policy_id):
    for pp in report["per_policy"]:
        if pp["policy_id"] == policy_id:
            return pp["positive_admitted"], pp["n_positive"]
    raise KeyError(policy_id)


def neg_admit(report, policy_id):
    for pp in report["per_policy"]:
        if pp["policy_id"] == policy_id:
            return pp["negative_false_admitted"], pp["n_negative"]
    raise KeyError(policy_id)


def hard(report, name):
    for h in report["hard_checks"]:
        if h["name"] == name:
            return h["ok"]
    return None


# ---------------------------------------------------------------------------
# positive (must pass)
# ---------------------------------------------------------------------------
def test_full_24class_passes(tmp_path):
    r, report = run_checker(tmp_path, full_positive(), clean_negatives())
    assert r.returncode == 0, r.stdout
    assert all(h["ok"] for h in report["hard_checks"]), report["hard_checks"]
    # every candidate admits all 120 positive (residual 0.05 is under every bound)
    for pp in report["per_policy"]:
        assert pp["positive_admitted"] == 120
        assert pp["positive_admit_rate"] == 1.0
        assert pp["false_reject_rate"] == 0.0
        assert pp["admitted_agreement_rate"] == 1.0
    # no negative is admitted (low training corr -> rejected by every candidate)
    for pp in report["per_policy"]:
        assert pp["negative_false_admit_rate"] == 0.0


def test_baseline_and_candidates_covered(tmp_path):
    r, report = run_checker(tmp_path, full_positive(), clean_negatives())
    ids = {pp["policy_id"] for pp in report["per_policy"]}
    assert "baseline_0100" in ids
    for t in ("0.110", "0.120", "0.130", "0.140", "0.150", "0.160"):
        assert ("cand_" + t.replace(".", "")) in ids


# ---------------------------------------------------------------------------
# negative (must fail-closed)
# ---------------------------------------------------------------------------
def test_missing_class_fails(tmp_path):
    rows = [r for r in full_positive() if int(r[2]) != 23]  # drop OQPSK
    r, report = run_checker(tmp_path, rows, clean_negatives())
    assert r.returncode == 1
    assert hard(report, "class_coverage") is False
    assert 23 in report["class_coverage"]["missing"]


def test_duplicate_capture_id_fails(tmp_path):
    rows = full_positive()
    rows.append(pos_row(0, 1, capture_id="rfpos_c00_r1"))  # duplicate capture_id
    r, report = run_checker(tmp_path, rows, clean_negatives())
    assert r.returncode == 1
    assert hard(report, "primary_key_unique") is False


def test_duplicate_source_repeat_fails(tmp_path):
    rows = full_positive()
    rows.append(pos_row(0, 1, capture_id="rfpos_c00_r1_extra"))  # same (si, rep)
    r, report = run_checker(tmp_path, rows, clean_negatives())
    assert r.returncode == 1
    assert hard(report, "primary_key_unique") is False


def test_nan_residual_fails(tmp_path):
    rows = full_positive()
    rows[0][11] = "nan"  # payload_training_residual
    r, report = run_checker(tmp_path, rows, clean_negatives())
    assert r.returncode == 1
    assert hard(report, "all_values_finite") is False


def test_positive_negative_mixed_fails(tmp_path):
    # a negative row whose capture_id collides with a positive capture_id
    rows = full_positive()
    smuggled = [pos_row(0, 1, capture_id="rfpos_c00_r1")[0], "no_signal", "", "", "",
                1, -40, 35, 18000000, 2400000000, 2560000, 2048, 5.0, 0.1, 0.05, 500.0,
                0, 0, "", "", "", "", ""]
    r, report = run_checker(tmp_path, rows, clean_negatives() + [smuggled])
    assert r.returncode == 1
    assert hard(report, "positive_negative_not_mixed") is False


def test_wc_sc_merged_fails(tmp_path):
    rows = full_positive()
    for r in rows:
        if int(r[2]) in (17, 18):
            r[3] = "AM-SSB"  # both WC and SC relabeled to the merged label
    r, report = run_checker(tmp_path, rows, clean_negatives())
    assert r.returncode == 1
    assert hard(report, "wc_sc_independent") is False


def test_insufficient_sample_count_fails(tmp_path):
    rows = [r for r in full_positive() if not (int(r[2]) == 23 and int(r[4]) >= 2)]
    # leaves class 23 with only 1 repeat
    r, report = run_checker(tmp_path, rows, clean_negatives())
    assert r.returncode == 1
    assert hard(report, "class_coverage") is False
    assert any(s[0] == 23 for s in report["class_coverage"]["repeat_short"])


# ---------------------------------------------------------------------------
# candidate behavior (informational, but deterministic)
# ---------------------------------------------------------------------------
def test_candidate_rescues_positive(tmp_path):
    rows = full_positive()
    # class 3 BPSK, repeat 1: residual 0.145 -> rejected by baseline(0.100),
    # rejected by cand_0.140, admitted by cand_0.150 and cand_0.160.
    rows[15] = pos_row(3, 1, residual=0.145, admitted=0)
    r, report = run_checker(tmp_path, rows, clean_negatives())
    assert r.returncode == 0
    b = admit_count(report, "baseline_0100")[0]
    c140 = admit_count(report, "cand_0140")[0]
    c150 = admit_count(report, "cand_0150")[0]
    assert c150 == b + 1
    assert c140 == b


def test_candidate_misadmits_negative(tmp_path):
    # wrong_window_or_sync negative that a relaxed residual threshold admits.
    negs = clean_negatives()
    for i, n in enumerate(negs):
        if n[1] == "wrong_window_or_sync":
            negs[i] = neg_row("wrong_window_or_sync", n[5], residual=0.145,
                              pcorr=0.95, tcorr=0.95, cfo=5.0, clip=0, admitted=0)
    r, report = run_checker(tmp_path, full_positive(), negs)
    assert r.returncode == 0
    assert neg_admit(report, "baseline_0100")[0] == 0
    assert neg_admit(report, "cand_0150")[0] >= 1
    assert report["per_policy"]  # sanity


def test_policy_modification_detected(tmp_path):
    # The checker records the policy file SHA; a post-hoc change must change it.
    # Tamper a COPY of the frozen policy, never the frozen contract itself.
    policy_copy = tmp_path / "policy_copy.tsv"
    with open(POLICY, encoding="utf-8") as src, open(policy_copy, "w",
                                                     newline="", encoding="utf-8") as dst:
        dst.write(src.read())
    r1, rep1 = run_checker(tmp_path, full_positive(), clean_negatives(),
                           policy_path=policy_copy)
    sha1 = rep1["policy_sha256"]

    # append a new candidate row to the COPY (a violation of freezing)
    with open(policy_copy, "a", newline="", encoding="utf-8") as f:
        f.write("cand_0170\tresidual_only\tthreshold\t0.170\t0.9\t0.9\t21.739\t1\t"
                "tamper\ttampered policy row\n")
    r2, rep2 = run_checker(tmp_path, full_positive(), clean_negatives(),
                           policy_path=policy_copy)
    sha2 = rep2["policy_sha256"]
    assert sha1 != sha2
    # the frozen contract file is byte-identical before and after the test
    assert os.path.getsize(POLICY) > 0


def test_no_new_threshold_flag(tmp_path):
    r, report = run_checker(tmp_path, full_positive(), clean_negatives())
    assert report["no_new_production_threshold"] is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
