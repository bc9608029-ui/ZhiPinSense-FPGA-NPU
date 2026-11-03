#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Package the fix10class24-classification-gate-separation1 delivery (offline, Part B).

The deployed board state this delivery overlays is the dc-ab1 INTEGRATED patch on top of
the npu-ab1 FULL tree.  This delivery is PURELY ADDITIVE: it adds ONE new shared header
(radioml_diagnostic_classify.hpp), REPLACES the two runners (single/dual) with their
Part-B-aware versions (which are byte-for-byte the dc-ab1 runners PLUS the additive
`--diagnostic-force-classify` diagnostic-bypass branch), and adds the contract + unified
judger + run script + host test + docs.  Production behaviour with the flag OFF is
IDENTICAL to dc-ab1: the 0.100 fidelity gate, 19-col board_results.tsv, gated/board_pred/
gate_reject semantics are all unchanged.

  PATCH package -- the exact Part B change set:
    board_package/radioml_diagnostic_classify.hpp    (NEW shared header: 7 bypass conditions
                                                      + try_diagnostic_apply)
    board_package/radioml_singlesdr_ab_runner.hpp    (dc-ab1 + Part B diagnostic branch)
    board_package/radioml_dualsdr_ab_runner.hpp      (dc-ab1 + Part B diagnostic branch)
    contract/classification_gate_separation_contract.{md,json}
    docs/M29_RML24_FIX10CLASS24_CLASSIFICATION_GATE_SEPARATION1_BOARDTEST.md
    host_tests/test_radioml_gate_separation.py       (host test, 7/7)
    scripts/judge_radioml_gate_separation.py         (unified judger: production/diagnostic/blind)
    scripts/run_radioml_gate_separation.sh           (single/dual x direct/dc x diag on/off)
    scripts/package_radioml_gate_separation1.py      (this packager)

No input package is delivered here: Part B reuses the dc-ab1 direct/dc input packages
byte-for-byte (the diagnostic bypass re-reads the SAME tx payload; it does not change the
TX payload or the recovery math).

Red lines stay byte-identical to the deployed base: the 0.100 fidelity gate, the 19-col
board_results.tsv, the frozen recovery headers (iq_rf_sync_recovery.hpp /
iq_dual_sdr_coarse_cfo_recovery.hpp), the frozen BF16 model, the frozen 480-frame
selection.  No model / preprocessor / recovery / threshold is touched; the ONLY relaxed
condition in Part B is a local copy's rec.valid before the verbatim iqrfrec::apply().

Run with:
    python -I scripts/package_radioml_gate_separation1.py
"""

import gzip
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DIST = os.path.join(ROOT, "dist")

# The deployed base this delivery overlays (npu-ab1 FULL tree; the dc-ab1 integrated
# patch already sits on top of it, and this delivery is additive to that).
BASE_DIR = os.path.abspath(os.path.join(
    ROOT, os.pardir,
    "fix10class24_original_radioml_npu_ab1_work",
    "sdr_rml24_fix10class24_original_radioml_npu_ab1"))

PATCH_NAME = "sdr_rml24_fix10class24_classification_gate_separation1_patch"
PATCH_SUMS_NAME = "FIX10CLASS24_CLASSIFICATION_GATE_SEPARATION1_PATCH_SHA256SUMS.txt"

EXPECTED_PATCH_FILES = (
    "board_package/radioml_diagnostic_classify.hpp",
    "board_package/radioml_singlesdr_ab_runner.hpp",
    "board_package/radioml_dualsdr_ab_runner.hpp",
    "contract/classification_gate_separation_contract.json",
    "contract/classification_gate_separation_contract.md",
    "docs/M29_RML24_FIX10CLASS24_CLASSIFICATION_GATE_SEPARATION1_BOARDTEST.md",
    "host_tests/test_radioml_gate_separation.py",
    "scripts/judge_radioml_gate_separation.py",
    "scripts/run_radioml_gate_separation.sh",
    "scripts/package_radioml_gate_separation1.py",
)

# The diagnostic header's single include must resolve against the deployed base (it is
# NOT in the patch; it comes from the npu-ab1 base tree).  The runners already resolve
# against the same base (they are the dc-ab1 runners + the additive Part B branch).
DIAG_INCLUDE_CLOSURE = (
    "board_package/iq_dual_sdr_coarse_cfo_recovery.hpp",
    "board_package/iq_rf_sync_recovery.hpp",
    "board_package/iq_rf_training_frame.hpp",
)

# Red-line headers that must NEVER appear in the change set (this delivery adds/replaces
# only the two runners + one new header; the frozen recovery math is reused, not shipped).
REDLINE_BASENAMES = (
    "iq_rf_sync_recovery.hpp", "iq_dual_sdr_coarse_cfo_recovery.hpp",
    "iq_rf_training_frame.hpp", "iq_rf_frame_layout.hpp",
    "iq_rf_loopback_transfer.hpp", "iq_rf_per_frame_recovery.hpp",
    "iq_rf_loopback_transfer_24class_bf16_fix10.hpp", "iq_fix10_canonical_frame.hpp",
    "iq_pc_tx_board_rx_transfer_fix10.hpp", "rml24_raw.hpp", "chain_common.hpp",
    "npu_classifier24.hpp", "board_common.hpp", "iq_digital_loopback.hpp",
    "iq_digital_loopback_sync.hpp", "rf_fix_helpers.hpp",
)

EXCLUDED_DIRS = ("__pycache__", "dist", ".git", "results")
EXCLUDED_SUFFIX = (".pyc",)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _entry_info(full, arc, is_dir):
    info = tarfile.TarInfo()
    info.name = arc
    st = os.lstat(full)
    info.size = 0 if is_dir else st.st_size
    info.mtime = 0
    info.mode = 0o755 if is_dir else (0o755 if arc.endswith(".sh") else 0o644)
    info.type = tarfile.DIRTYPE if is_dir else tarfile.REGTYPE
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def make_tar_flat(stage, tar_path):
    raw = tar_path + ".tmp.tar"
    entries = []
    for dirpath, dirnames, filenames in os.walk(stage):
        dirnames.sort()
        filenames.sort()
        for d in dirnames:
            entries.append((os.path.relpath(os.path.join(dirpath, d), stage)
                            .replace(os.sep, "/"), True))
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), stage).replace(os.sep, "/")
            entries.append((rel, False))
    entries.sort(key=lambda e: e[0])
    with tarfile.open(raw, "w", format=tarfile.GNU_FORMAT) as t:
        for rel, is_dir in entries:
            full = os.path.join(stage, rel.replace("/", os.sep))
            info = _entry_info(full, rel, is_dir)
            if is_dir:
                t.addfile(info)
            else:
                with open(full, "rb") as f:
                    t.addfile(info, f)
    with open(raw, "rb") as fin:
        with gzip.GzipFile(filename="", mode="wb", fileobj=open(tar_path, "wb"),
                           compresslevel=9, mtime=0) as gz:
            shutil.copyfileobj(fin, gz)
    os.remove(raw)


def build_tar_deterministic(stage, tar_path):
    r1 = tar_path + ".run1"
    r2 = tar_path + ".run2"
    make_tar_flat(stage, r1)
    make_tar_flat(stage, r2)
    with open(r1, "rb") as a, open(r2, "rb") as b:
        if a.read() != b.read():
            sys.exit("DETERMINISM FAILED: %s" % tar_path)
    os.remove(r2)
    os.replace(r1, tar_path)


def write_sums(stage, sums_name):
    rels = []
    for dirpath, dirnames, filenames in os.walk(stage):
        dirnames[:] = sorted(
            d for d in dirnames
            if os.path.relpath(os.path.join(dirpath, d), stage).replace(os.sep, "/")
            not in EXCLUDED_DIRS)
        for name in filenames:
            if name.endswith(EXCLUDED_SUFFIX):
                continue
            rels.append(os.path.relpath(os.path.join(dirpath, name), stage)
                        .replace(os.sep, "/"))
    rels = [r for r in sorted(rels) if r != sums_name]
    lines = ["%s *%s\n" % (sha256_of(os.path.join(stage, rel.replace("/", os.sep))), rel)
             for rel in rels]
    with open(os.path.join(stage, sums_name), "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(sorted(lines)))
    return len(rels)


def verify_tar_flat(tar_path, sums_name):
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(tar_path, "r:gz") as t:
            t.extractall(td, filter="data")
        ok = 0
        bad = 0
        with open(os.path.join(td, sums_name), "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                hx, _, rel = line.partition(" *")
                if sha256_of(os.path.join(td, rel.replace("/", os.sep))) == hx:
                    ok += 1
                else:
                    bad += 1
                    print("  MISMATCH: %s" % rel, file=sys.stderr)
        return (bad == 0, ok + bad, ok)


def _fail(label, violations):
    print(label + " FAILED:", file=sys.stderr)
    for v in violations:
        print("  " + v, file=sys.stderr)
    sys.exit(1)


def audit_patch_files_present():
    bad = []
    for rel in EXPECTED_PATCH_FILES:
        src = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(src):
            bad.append(rel + " (missing: " + src + ")")
    if bad:
        _fail("patch-file-presence audit", bad)
    print("patch-file-presence audit: OK (%d files present)" % len(EXPECTED_PATCH_FILES))


def audit_no_redline_headers():
    bad = []
    for rel in EXPECTED_PATCH_FILES:
        if not rel.endswith((".hpp", ".cpp")):
            continue
        base = os.path.basename(rel)
        if base in REDLINE_BASENAMES:
            bad.append(rel + " is a red-line header")
    if bad:
        _fail("no-red-line-header audit", bad)
    print("no-red-line-header audit: OK (change set adds only diagnostic header + "
          "two Part-B runners, no frozen recovery math)")


def audit_include_closure():
    bad = []
    if not os.path.isdir(BASE_DIR):
        bad.append("missing base tree: " + BASE_DIR)
    else:
        for rel in DIAG_INCLUDE_CLOSURE:
            if not os.path.isfile(os.path.join(BASE_DIR, rel.replace("/", os.sep))):
                bad.append(rel + " (missing in base npu-ab1 tree)")
    if bad:
        _fail("include-closure audit", bad)
    print("include-closure audit: OK (%d diagnostic-header base deps present)"
          % len(DIAG_INCLUDE_CLOSURE))


def audit_part_b_source():
    """Both runners must carry the additive Part B branch AND still be a strict superset
    of the dc-ab1 runners (the dc markers must remain)."""
    bad = []
    diag = open(os.path.join(ROOT, "board_package/radioml_diagnostic_classify.hpp"),
                encoding="utf-8").read()
    for marker in ("is_diagnostic_bypassable", "try_diagnostic_apply",
                   "PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH", "rec_diag.valid = true",
                   "iqrfrec::apply(aligned, rec_diag)",
                   "kClassificationLayerDiagnostic"):
        if marker not in diag:
            bad.append("diagnostic header missing marker: " + marker)
    for name in ("radioml_singlesdr_ab_runner.hpp", "radioml_dualsdr_ab_runner.hpp"):
        src = open(os.path.join(ROOT, "board_package", name), encoding="utf-8").read()
        for marker in ("--diagnostic-force-classify", "board_diagnostic_results.tsv",
                       "diagnostic_bypass_total", "diagnostic_bypass_classified",
                       "diagnostic_bypass_correct", "diagnostic_bypass_repeat_det",
                       "diagnostic_bypass_refused", "diagnostic_bypass_apply_failed",
                       "is_diagnostic_bypassable", "try_diagnostic_apply",
                       "board_pred_diag", "finite_diag", "repeat_deterministic",
                       "classification_layer", "diagnostic_gate_bypass", "label_correct"):
            if marker not in src:
                bad.append(name + " missing Part B marker: " + marker)
        # still a superset of dc-ab1: --adaptation gate + DC branch remain
        for marker in ("--adaptation", "reconstruct_dc_window", "rml24dc::"):
            if marker not in src:
                bad.append(name + " lost dc-ab1 marker: " + marker)
    if bad:
        _fail("part-b-source audit", bad)
    print("part-b-source audit: OK (both runners carry additive Part B branch; "
          "dc-ab1 markers intact)")


def audit_host_test():
    r = subprocess.run(
        [sys.executable, "-I",
         os.path.join(ROOT, "host_tests", "test_radioml_gate_separation.py")],
        capture_output=True, text=True)
    if r.returncode != 0 or "RADIOML_GATE_SEPARATION_SELFTEST 7/7 passed" not in r.stdout:
        _fail("host-test audit",
              ["test_radioml_gate_separation.py rc=%d\n%s\n%s"
               % (r.returncode, r.stdout[-2000:], r.stderr[-2000:])])
    print("host-test audit: OK (test_radioml_gate_separation.py 7/7 passed)")


def build_patch_package():
    work = tempfile.mkdtemp(prefix="pkg_gate_sep1_patch_")
    try:
        stage = os.path.join(work, PATCH_NAME)
        os.makedirs(stage, exist_ok=True)
        for rel in EXPECTED_PATCH_FILES:
            src = os.path.join(ROOT, rel.replace("/", os.sep))
            dst = os.path.join(stage, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        n = write_sums(stage, PATCH_SUMS_NAME)
        tar_path = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        build_tar_deterministic(stage, tar_path)
        print("determinism: OK (patch tarball built twice, byte-identical)")
        shutil.copy2(os.path.join(stage, PATCH_SUMS_NAME),
                     os.path.join(DIST, PATCH_NAME + "_SHA256SUMS.txt"))
        ok, total, good = verify_tar_flat(tar_path, PATCH_SUMS_NAME)
        print("  %-48s files=%d ok=%d %s"
              % ("gate-separation1 patch", total, good, "PASS" if ok else "FAIL"))
        if not ok:
            sys.exit(1)
        print("  %-48s %d content-files  sha256=%s"
              % ("gate-separation1 patch", n, sha256_of(tar_path)))
        print("  %s" % tar_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    if not os.path.isdir(BASE_DIR):
        sys.exit("missing base tree: %s" % BASE_DIR)
    audit_patch_files_present()
    audit_no_redline_headers()
    audit_include_closure()
    audit_part_b_source()
    audit_host_test()
    os.makedirs(DIST, exist_ok=True)
    print("== patch package ==")
    build_patch_package()
    print("== summary ==")
    print("  base npu-ab1 tree         %s" % BASE_DIR)
    print("  deliverable               %s" % os.path.join(DIST, PATCH_NAME + ".tar.gz"))


if __name__ == "__main__":
    main()
