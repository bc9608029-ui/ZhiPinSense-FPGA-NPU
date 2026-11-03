"""test_report_evidence.py -- pytest for the rml24-report-evidence1 ledger.

Run:  python -I -m pytest -q host_tests/test_report_evidence.py
Each test asserts one of the 14 check classes, plus two meta checks.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(HERE), "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import check_report_evidence as ce  # noqa: E402

RESULTS = None


def _results():
    global RESULTS
    if RESULTS is None:
        RESULTS = ce.check()
    return RESULTS


def _ok(name):
    ok, detail = _results()[name]
    assert ok, "%s failed: %s" % (name, detail)


def test_01_tree_structure():
    _ok("tree_structure")


def test_02_evidence_levels():
    _ok("evidence_levels")


def test_03_terminology():
    _ok("terminology")


def test_04_source_inventory():
    _ok("source_inventory")


def test_05_tree_hash_consistency():
    _ok("tree_hash_consistency")


def test_06_claim_count():
    _ok("claim_count")


def test_07_claim_evidence_valid():
    _ok("claim_evidence_valid")


def test_08_sha_format():
    _ok("sha_format")


def test_09_layering_integrity():
    _ok("layering_integrity")


def test_10_forbidden_tokens():
    _ok("forbidden_tokens")


def test_11_tables():
    _ok("tables")


def test_12_diagrams():
    _ok("diagrams")


def test_13_report_skeleton():
    _ok("report_skeleton")


def test_14_final_status_token():
    _ok("final_status_token")


# --- meta checks -----------------------------------------------------------

def test_15_no_not_verified_in_verified_conclusions():
    cur = ce._read("report/CURRENT_VERIFIED_CONCLUSIONS.md")
    assert "NOT_VERIFIED" not in cur


def test_16_all_claims_reference_present_or_not_verified_file():
    # every claim's evidence_file is either a real path on disk (under F:\嵌赛) or
    # one of the ledger's own files; sha is never a bare copy of an old report number.
    for r in ce._claim_rows():
        claim, lvl, f, sha, status = r[0], r[3], r[4], r[5], r[7]
        assert lvl in ce._declared_levels(), claim
        assert status in ce.ALLOWED_STATUS, claim
        if sha not in ("NOT_VERIFIED", "SOURCE_NOT_PRESENT"):
            assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), claim
