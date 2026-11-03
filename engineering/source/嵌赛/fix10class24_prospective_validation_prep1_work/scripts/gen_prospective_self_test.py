#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_prospective_self_test.py — generate the Phase F synthetic self-test artifacts:
a full 24-class positive results table, a 13-type negative results table, and the
checker's report, written into results/prospective_validation_prep1/self_test/.

Reuses the row builders from host_tests/test_fix10class24_prospective_validation.py
so the self-test fixtures are byte-identical to the ones the pytest suite exercises.
No board, no SDR, no real capture.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
HOST_TESTS = os.path.join(ROOT, "host_tests")
SCRIPTS = HERE
CONTRACTS = os.path.join(ROOT, "contracts", "prospective_validation_v1")
OUT = os.path.join(ROOT, "results", "prospective_validation_prep1", "self_test")

sys.path.insert(0, HOST_TESTS)
sys.path.insert(0, SCRIPTS)

import test_fix10class24_prospective_validation as t  # noqa: E402

CHECKER = os.path.join(SCRIPTS, "check_fix10class24_prospective_validation.py")
POLICY = os.path.join(CONTRACTS, "candidate_gate_policy.tsv")
IDENTITY = os.path.join(CONTRACTS, "clean24_identity.tsv")


def main():
    os.makedirs(OUT, exist_ok=True)
    pos_path = os.path.join(OUT, "synthetic_positive_results.tsv")
    neg_path = os.path.join(OUT, "synthetic_negative_results.tsv")

    t.write_tsv(pos_path, t.POS_HEADER, t.full_positive())
    t.write_tsv(neg_path, t.NEG_HEADER, t.clean_negatives())

    r = subprocess.run([sys.executable, CHECKER,
                        "--positive-results", pos_path,
                        "--negative-results", neg_path,
                        "--policy", POLICY,
                        "--identity", IDENTITY,
                        "--out-dir", OUT],
                       capture_output=True, text=True)

    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
