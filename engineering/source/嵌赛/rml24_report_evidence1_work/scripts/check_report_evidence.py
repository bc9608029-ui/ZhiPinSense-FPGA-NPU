#!/usr/bin/env python3
"""check_report_evidence.py -- M29 RML24 final-report evidence-ledger checker.

Validates the deliverable tree produced by the rml24-report-evidence1 task.
Pure stdlib; run with `python -I scripts/check_report_evidence.py`.

14 check classes (one dict entry per class; key = check name):
  1. tree_structure           all required files present
  2. evidence_levels          evidence_level_v1.tsv has exactly 12 levels, ranks 0..11
  3. terminology              result_terminology_v1.md present + documents layering + forbidden tokens
  4. source_inventory         10 trees, 9 PRESENT + enclosure-prep2 SOURCE_NOT_PRESENT
  5. tree_hash_consistency    non-concurrent trees before==after; PRESENT -> 64-hex SHA; missing -> SOURCE_NOT_PRESENT
  6. claim_count              exactly 21 claims, ids C01..C21 unique
  7. claim_evidence_valid     each claim level is a declared level; status in allowed set
  8. sha_format               claim-matrix SHA is 64-hex | NOT_VERIFIED | SOURCE_NOT_PRESENT
  9. layering_integrity       L9/L10/L11 claims must be PENDING/NOT_VERIFIED (never VERIFIED)
 10. forbidden_tokens         no forbidden verdict token in conclusion-bearing files
 11. tables                   exactly 9 result tables, each a parseable TSV with header
 12. diagrams                 3 mermaid files present and non-empty
 13. report_skeleton          report draft/current/pending present with PENDING placeholders
 14. final_status_token       audit declares exactly the allowed max status, nothing higher
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ALLOWED_STATUS = {"VERIFIED", "VERIFIED_NEGATIVE", "PENDING", "NOT_VERIFIED"}

# Forbidden verdict tokens.  Scanned in conclusion-bearing files only (see
# FORBIDDEN_SCAN); the terminology contract DEFINES them and the source-tree
# inventory records OTHER tasks' historical status tokens, so neither is scanned.
FORBIDDEN_TOKENS = [
    "SMOKE-PASS", "RF-PASS", "24CLASS-PASS", "RXONLY-PASS", "RF_PATH_PROVEN",
    "NPU_PASS", "PROJECT_COMPLETE", "FINAL_PASS", "FINAL_COMPLETE",
]

# A line that names a forbidden token only to PROHIBIT it (a red-line declaration,
# e.g. "禁写 SMOKE-PASS" or "No ... token may be written") is not an assertion of
# that status, so the forbidden-token scan skips such lines.
PROHIBITION_MARKERS = (
    "禁写", "禁止", "不得", "must not", "may not", "may be written", "forbidden",
    "not write", "never write", "don't write",
)

MAX_STATUS = "M29-RML24-REPORT-EVIDENCE-LEDGER-READY-FOR-ROOT-CAUSE-INSERTION"

# Trees under concurrent modification by OTHER tasks (not this ledger).  Their
# before/after snapshots may legitimately differ; the read-only guarantee for them
# is process-level (this ledger wrote zero bytes), not fingerprint-level.
CONCURRENT_TREES = {
    "fix10class24_rxresidual_audit1_work",   # main line (rxresidual-audit1) actively writing
    "constellation_ui_desktop1_work",        # UI desktop agent (task 二) actively writing
}

REQUIRED_FILES = [
    "contracts/evidence_level_v1.tsv",
    "contracts/result_terminology_v1.md",
    "evidence/source_tree_inventory.tsv",
    "evidence/claim_evidence_matrix.tsv",
    "evidence/source_tree_hash_before.tsv",
    "evidence/source_tree_hash_after.tsv",
    "architecture/dual_sdr_validation_architecture.mmd",
    "architecture/final_receiver_architecture.mmd",
    "architecture/evidence_flow.mmd",
    "report/RML24_SYSTEM_REPORT_DRAFT.md",
    "report/CURRENT_VERIFIED_CONCLUSIONS.md",
    "report/PENDING_EVIDENCE.md",
    "scripts/check_report_evidence.py",
    "host_tests/test_report_evidence.py",
    "docs/M29_RML24_REPORT_EVIDENCE1_AUDIT.md",
] + ["report/tables/t%02d_%s.tsv" % (i, n) for i, n in enumerate([
    "bf16_model_identity", "host_bf16_24class_accuracy", "npu_mapping_summary",
    "canonical_frame_components", "canonical_replay_fields",
    "phase_d_residual_decomposition", "rx_frontend_sweep_board_results",
    "packaging_determinism", "red_line_headers"], start=1)]

# Files that assert conclusions/status (scanned for forbidden tokens).
FORBIDDEN_SCAN = [
    "evidence/claim_evidence_matrix.tsv",
    "report/RML24_SYSTEM_REPORT_DRAFT.md",
    "report/CURRENT_VERIFIED_CONCLUSIONS.md",
    "report/PENDING_EVIDENCE.md",
    "docs/M29_RML24_REPORT_EVIDENCE1_AUDIT.md",
] + ["report/tables/%s" % f for f in sorted(os.listdir(os.path.join(ROOT, "report", "tables"))) if f.endswith(".tsv")]

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _path(rel: str) -> str:
    return os.path.join(ROOT, rel.replace("/", os.sep))


def _read(rel: str) -> str:
    with open(_path(rel), "r", encoding="utf-8") as f:
        return f.read()


def _rows(rel: str):
    """Return list of non-comment, non-empty rows split on tabs (header included)."""
    rows = []
    for line in _read(rel).splitlines():
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        rows.append(line.split("\t"))
    return rows


def _forbidden_in_text(txt: str):
    """Forbidden tokens used as assertions (skips prohibition lines)."""
    hits = []
    for line in txt.splitlines():
        low = line.lower()
        if any(m in low for m in PROHIBITION_MARKERS):
            continue
        for tok in FORBIDDEN_TOKENS:
            if tok in line:
                hits.append(tok)
        for m in re.findall(r"FINAL_[A-Z_]+", line):
            hits.append(m)
    return hits


# ---------------------------------------------------------------- checks ---

def check_tree_structure():
    missing = [f for f in REQUIRED_FILES if not os.path.isfile(_path(f))]
    return (not missing), ("missing=%s" % missing if missing else "all %d files present" % len(REQUIRED_FILES))


def check_evidence_levels():
    rows = _rows("contracts/evidence_level_v1.tsv")
    if not rows or rows[0][0] != "rank":
        return False, "no header"
    body = rows[1:]
    ranks = [r[0] for r in body]
    ok = len(body) == 12 and ranks == [str(i) for i in range(12)]
    return ok, ("12 levels ranks 0..11" if ok else "body=%d ranks=%s" % (len(body), ranks))


def check_terminology():
    txt = _read("contracts/result_terminology_v1.md")
    ok = all(s in txt for s in ["conclusion", "limitation", "host", "board-NPU", "NOT_VERIFIED", "SOURCE_NOT_PRESENT"])
    has_forbidden = all(t in txt for t in ["SMOKE-PASS", "RF-PASS", "PROJECT_COMPLETE"])
    return (ok and has_forbidden), ("layering + terminology documented" if ok and has_forbidden else "missing terms")


def check_source_inventory():
    rows = _rows("evidence/source_tree_inventory.tsv")
    body = rows[1:]
    present = [r for r in body if r[1] == "PRESENT"]
    missing = [r for r in body if r[1] == "SOURCE_NOT_PRESENT"]
    ok = len(body) == 10 and len(present) == 9 and len(missing) == 1 and missing[0][0] == "enclosure-prep2"
    return ok, ("10 trees: 9 PRESENT + enclosure-prep2 SOURCE_NOT_PRESENT" if ok else "present=%d missing=%s" % (len(present), [r[0] for r in missing]))


def _hash_rows(rel):
    return {r[0]: (r[1], r[2], r[3]) for r in _rows(rel)[1:]}


def check_tree_hash_consistency():
    b = _hash_rows("evidence/source_tree_hash_before.tsv")
    a = _hash_rows("evidence/source_tree_hash_after.tsv")
    if set(b) != set(a):
        return False, "tree set mismatch before/after"
    bad = []
    for t in b:
        status, cnt, h = b[t]
        # Non-concurrent trees must be byte-stable (before == after).  Concurrent
        # trees are actively modified by OTHER tasks, so their snapshots may differ.
        if t not in CONCURRENT_TREES and b[t] != a[t]:
            bad.append(t + ":changed")
        if status == "PRESENT" and not HEX64.match(h):
            bad.append(t + ":sha")
        if status == "SOURCE_NOT_PRESENT" and h != "SOURCE_NOT_PRESENT":
            bad.append(t + ":missing-token")
    return (not bad), ("non-concurrent trees unchanged; SHAs well-formed" if not bad else "bad=%s" % bad)


def _claim_rows():
    return _rows("evidence/claim_evidence_matrix.tsv")[1:]


def check_claim_count():
    rows = _claim_rows()
    ids = [r[0] for r in rows]
    expected = ["C%02d" % i for i in range(1, 22)]
    ok = len(rows) == 21 and ids == expected and len(set(ids)) == 21
    return ok, ("21 claims C01..C21 unique" if ok else "n=%d ids=%s" % (len(rows), ids[:5]))


def _declared_levels():
    return {r[1] for r in _rows("contracts/evidence_level_v1.tsv")[1:]}


def check_claim_evidence_valid():
    levels = _declared_levels()
    bad = []
    for r in _claim_rows():
        if len(r) < 8:
            bad.append(r[0] + ":cols")
            continue
        if r[3] not in levels:
            bad.append(r[0] + ":level=" + r[3])
        if r[7] not in ALLOWED_STATUS:
            bad.append(r[0] + ":status=" + r[7])
    return (not bad), ("all levels/statuses valid" if not bad else "bad=%s" % bad[:5])


def check_sha_format():
    bad = []
    for r in _claim_rows():
        sha = r[5]
        if sha in ("NOT_VERIFIED", "SOURCE_NOT_PRESENT"):
            continue
        if not HEX64.match(sha):
            bad.append(r[0])
    return (not bad), ("all claim SHAs well-formed" if not bad else "bad=%s" % bad)


def check_layering_integrity():
    ranks = {r[1]: int(r[0]) for r in _rows("contracts/evidence_level_v1.tsv")[1:]}
    bad = []
    for r in _claim_rows():
        lvl = r[3]
        if ranks.get(lvl, 0) >= 9 and r[7] in ("VERIFIED", "VERIFIED_NEGATIVE"):
            bad.append(r[0] + ":" + lvl + ":" + r[7])
    return (not bad), ("no L9/L10/L11 claim marked VERIFIED" if not bad else "bad=%s" % bad)


def check_forbidden_tokens():
    hits = []
    for rel in FORBIDDEN_SCAN:
        for tok in _forbidden_in_text(_read(rel)):
            hits.append("%s:%s" % (rel, tok))
    return (not hits), ("no forbidden verdict token" if not hits else "hits=%s" % hits[:5])


def check_tables():
    d = os.path.join(ROOT, "report", "tables")
    files = sorted(f for f in os.listdir(d) if f.endswith(".tsv"))
    bad = []
    for f in files:
        rows = _rows("report/tables/" + f)
        if not rows or not all(len(r) >= 2 for r in rows[:2]):
            bad.append(f)
    ok = len(files) == 9 and not bad
    return ok, ("9 tables parseable" if ok else "files=%d bad=%s" % (len(files), bad))


def check_diagrams():
    d = os.path.join(ROOT, "architecture")
    files = sorted(f for f in os.listdir(d) if f.endswith(".mmd"))
    bad = [f for f in files if not os.path.getsize(os.path.join(d, f))]
    ok = len(files) == 3 and not bad
    return ok, ("3 non-empty diagrams" if ok else "files=%d bad=%s" % (len(files), bad))


def check_report_skeleton():
    draft = _read("report/RML24_SYSTEM_REPORT_DRAFT.md")
    cur = _read("report/CURRENT_VERIFIED_CONCLUSIONS.md")
    placeholders = ["[PENDING_RXRESIDUAL_AUDIT]", "[PENDING_UI_DESKTOP_RESULTS]",
                    "[PENDING_24CLASS_RF_PROSPECTIVE_VALIDATION]", "[PENDING_FPGA_UTILIZATION_REPORT]"]
    ok = all(p in draft for p in placeholders) and "Not yet formed" in draft and "NOT claimed" in cur
    return ok, ("draft + current + pending present, placeholders wired" if ok else "skeleton incomplete")


def check_final_status_token():
    audit = _read("docs/M29_RML24_REPORT_EVIDENCE1_AUDIT.md")
    ok = MAX_STATUS in audit and not _forbidden_in_text(audit)
    return ok, ("max status declared exactly" if ok else "status missing or too high")


CHECKS = [
    ("tree_structure", check_tree_structure),
    ("evidence_levels", check_evidence_levels),
    ("terminology", check_terminology),
    ("source_inventory", check_source_inventory),
    ("tree_hash_consistency", check_tree_hash_consistency),
    ("claim_count", check_claim_count),
    ("claim_evidence_valid", check_claim_evidence_valid),
    ("sha_format", check_sha_format),
    ("layering_integrity", check_layering_integrity),
    ("forbidden_tokens", check_forbidden_tokens),
    ("tables", check_tables),
    ("diagrams", check_diagrams),
    ("report_skeleton", check_report_skeleton),
    ("final_status_token", check_final_status_token),
]


def check():
    results = {}
    for name, fn in CHECKS:
        ok, detail = fn()
        results[name] = (ok, detail)
    return results


def main():
    results = check()
    failures = 0
    for name, (ok, detail) in results.items():
        print("%-24s %s  %s" % (name, "PASS" if ok else "FAIL", detail))
        if not ok:
            failures += 1
    print("-" * 60)
    print("SUMMARY: %d/%d checks passed" % (len(results) - failures, len(results)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
