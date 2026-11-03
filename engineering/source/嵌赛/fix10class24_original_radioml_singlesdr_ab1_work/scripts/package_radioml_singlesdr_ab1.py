#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Package the fix10class24-original-radioml-singlesdr-ab1 board-test delivery (offline).

The deployed board state is the npu-ab1 tree (tx-rms-sweep1 + npu-ab1 PATCH + scalarwl-4way
PATCH).  This delivery is PURELY ADDITIVE on top of it (deletions empty), and delivers the
SINGLE-SDR producer that the dualsdr fork deliberately deferred ("后续集成").  It produces
TWO deterministic FLAT tarballs (PATCH + INPUTS, each with its own SHA256, like npu-ab1):

  PATCH package  -- the exact change set (9 new + 2 changed + 4 vendored-verbatim files):
    board_package/radioml_singlesdr_ab_loader.hpp        (fail-closed 18-col TX-payload loader)
    board_package/radioml_singlesdr_ab_runner.hpp        (single-SDR RF runner; real NPU only)
    board_package/gate9_phase.hpp                        (new phase predicate, 1-line add)
    board_package/board_gate9_full_chain_rml23.cpp       (include + wrapper + dispatch + error-text)
    scripts/judge_radioml_singlesdr.py                   (4-arm A/D/C/S judger)
    scripts/run_radioml_singlesdr_ab.sh                  (board orchestration, single-SDR)
    scripts/package_radioml_singlesdr_ab1.py             (this packager)
    docs/M29_RML24_FIX10CLASS24_ORIGINAL_RADIOML_SINGLESDR_AB1_BOARDTEST.md
    host_tests/test_radioml_singlesdr_ab1.py             (host test, 10/10)
    contract/tx_derived_conversion_contract.{md,json}    (vendored verbatim from dualsdr)
    scripts/radioml_dualsdr_{common,burst}.py            (vendored verbatim)
    scripts/export_radioml_dualsdr_tx_payload.py         (vendored verbatim)
    scripts/digital_roundtrip_radioml_dualsdr.py         (vendored verbatim)

Red lines stay byte-identical to the deployed base: the 17 recovery/runner headers, the
24-class BF16 model json/raw, the 0.100 fidelity gate, the frozen assets, the canonical CI16
components.  No model / preprocessor / recovery / threshold is touched.

INPUTS package -- the TX-payload DATA package (480 x <sid>.i16 + tx_manifest.tsv +
SHA256SUMS.txt): the dualsdr fork's authoritative results/tx_payload/, re-verified against
its SHA256SUMS.txt and re-packaged VERBATIM (the TX-derived conversion rules are never
re-derived here).

Run with:
    python3 -I scripts/package_radioml_singlesdr_ab1.py
"""

import difflib
import gzip
import hashlib
import os
import re
import shutil
import sys
import tarfile
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DIST = os.path.join(ROOT, "dist")

# The deployed board state this delivery overlays (on-disk; already = npu-ab1 FULL).
BASE_DIR = os.path.abspath(os.path.join(
    ROOT, os.pardir,
    "fix10class24_original_radioml_npu_ab1_work",
    "sdr_rml24_fix10class24_original_radioml_npu_ab1"))

# The dualsdr fork (single authority for the TX-derived contract + vendored scripts).
DUALSDR_DIR = os.path.abspath(os.path.join(
    ROOT, os.pardir, "fix10class24_original_radioml_dualsdr_ab1_work"))

PATCH_NAME = "sdr_rml24_fix10class24_original_radioml_singlesdr_ab1_patch"
PATCH_SUMS_NAME = "FIX10CLASS24_ORIGINAL_RADIOML_SINGLESDR_AB1_PATCH_SHA256SUMS.txt"

# The board's --input-dir DATA package (independent of the PATCH, like npu-ab1's
# *_inputs.tar.gz): re-packaged from the dualsdr fork's authoritative TX payload.
INPUTS_NAME = "sdr_rml24_fix10class24_original_radioml_singlesdr_ab1_inputs"
INPUTS_SUMS_NAME = "FIX10CLASS24_ORIGINAL_RADIOML_SINGLESDR_AB1_INPUTS_SHA256SUMS.txt"

# The exact change set this delivery must produce, nothing else.
EXPECTED_PATCH_FILES = (
    "board_package/radioml_singlesdr_ab_loader.hpp",
    "board_package/radioml_singlesdr_ab_runner.hpp",
    "board_package/gate9_phase.hpp",
    "board_package/board_gate9_full_chain_rml23.cpp",
    "contract/tx_derived_conversion_contract.json",
    "contract/tx_derived_conversion_contract.md",
    "docs/M29_RML24_FIX10CLASS24_ORIGINAL_RADIOML_SINGLESDR_AB1_BOARDTEST.md",
    "host_tests/test_radioml_singlesdr_ab1.py",
    "scripts/digital_roundtrip_radioml_dualsdr.py",
    "scripts/export_radioml_dualsdr_tx_payload.py",
    "scripts/judge_radioml_singlesdr.py",
    "scripts/package_radioml_singlesdr_ab1.py",
    "scripts/radioml_dualsdr_burst.py",
    "scripts/radioml_dualsdr_common.py",
    "scripts/run_radioml_singlesdr_ab.sh",
)

# Files vendored VERBATIM from the dualsdr fork (same relative path in both trees).
VENDORED_VERBATIM = (
    "contract/tx_derived_conversion_contract.json",
    "contract/tx_derived_conversion_contract.md",
    "scripts/radioml_dualsdr_common.py",
    "scripts/radioml_dualsdr_burst.py",
    "scripts/export_radioml_dualsdr_tx_payload.py",
    "scripts/digital_roundtrip_radioml_dualsdr.py",
)

# The two MODIFIED files: they must differ from base by EXACTLY the intended hunks.
CHANGED_FILES = (
    "board_package/gate9_phase.hpp",
    "board_package/board_gate9_full_chain_rml23.cpp",
)

# Production headers my runner/loader must resolve against the deployed base (i.e. I
# must NOT have touched or omitted them).  A missing entry = include-closure failure.
RUNNER_BASE_HEADERS = (
    "board_package/chain_common.hpp",
    "board_package/npu_classifier24.hpp",
    "board_package/board_common.hpp",
    "board_package/iq_digital_loopback.hpp",
    "board_package/iq_digital_loopback_sync.hpp",
    "board_package/iq_rf_per_frame_recovery.hpp",
    "board_package/iq_rf_frame_layout.hpp",
    "board_package/iq_rf_loopback_transfer.hpp",
    "board_package/iq_dual_sdr_coarse_cfo_recovery.hpp",
    "board_package/iq_pc_tx_board_rx_transfer_fix10.hpp",
    "board_package/iq_fix10_canonical_frame.hpp",
    "board_package/iq_rf_loopback_transfer_24class_bf16_fix10.hpp",
    "board_package/rml24_raw.hpp",
    "board_package/rf_fix_helpers.hpp",
    "sdr_adapter/latency_stats.hpp",
    "sdr_adapter/resource_snapshot.hpp",
    "sdr_adapter/pluto_device.hpp",
    "sdr_adapter/device_state_guard.hpp",
    "sdr_adapter/sha256.hpp",
)

EXCLUDED_DIRS = ("__pycache__", "dist", ".git", "results")
EXCLUDED_SUFFIX = (".pyc",)

_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"')


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def list_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if os.path.relpath(os.path.join(dirpath, d), root).replace(os.sep, "/")
            not in EXCLUDED_DIRS)
        for name in filenames:
            if name.endswith(EXCLUDED_SUFFIX):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
            out.append(rel)
    return sorted(out)


def _gzip(raw, tar_path):
    with open(raw, "rb") as fin:
        with gzip.GzipFile(filename="", mode="wb", fileobj=open(tar_path, "wb"),
                           compresslevel=9, mtime=0) as gz:
            shutil.copyfileobj(fin, gz)
    os.remove(raw)


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
    _gzip(raw, tar_path)


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
    rels = [r for r in list_files(stage) if r != sums_name]
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


def audit_change_set():
    actual = [r for r in list_files(ROOT)
              if r != PATCH_SUMS_NAME and not r.startswith("dist/")]
    exp = sorted(EXPECTED_PATCH_FILES)
    if actual != exp:
        _fail("change-set audit", [
            "expected %d files=%s" % (len(exp), exp),
            "actual   %d files=%s" % (len(actual), actual)])
    print("change-set audit: OK (%d files, exactly as expected)" % len(actual))


def audit_vendored_verbatim():
    bad = []
    for rel in VENDORED_VERBATIM:
        mine = os.path.join(ROOT, rel.replace("/", os.sep))
        theirs = os.path.join(DUALSDR_DIR, rel.replace("/", os.sep))
        if not os.path.exists(theirs):
            bad.append(rel + " (missing in dualsdr fork)")
        elif sha256_of(mine) != sha256_of(theirs):
            bad.append(rel + " (differs from dualsdr fork)")
    if bad:
        _fail("vendored-verbatim audit", bad)
    print("vendored-verbatim audit: OK (%d files byte-identical to dualsdr fork)"
          % len(VENDORED_VERBATIM))


def audit_changed_files():
    # gate9_phase.hpp: exactly the 1-line -> 2-line predicate change.
    base = open(os.path.join(BASE_DIR, "board_package/gate9_phase.hpp"),
                encoding="utf-8").read().splitlines()
    mine = open(os.path.join(ROOT, "board_package/gate9_phase.hpp"),
                encoding="utf-8").read().splitlines()
    expected = (base[:26] +
                ['           p == "radioml-original-npu-ab-24class-bf16-fix10" ||',
                 '           p == "radioml-original-singlesdr-ab-24class-bf16-fix10";'] +
                base[27:])
    if mine != expected:
        _fail("gate9_phase.hpp red-line audit", [
            "diff vs base:\n" + "\n".join(difflib.unified_diff(
                base, mine, "base", "mine", lineterm=""))])
    print("gate9_phase.hpp red-line audit: OK (single predicate line added, nothing else)")

    # board_gate9_full_chain_rml23.cpp: exactly 4 hunks (include + wrapper + error-text
    # + dispatch); only ONE line removed (the old error text); 59 lines added.
    base = open(os.path.join(BASE_DIR, "board_package/board_gate9_full_chain_rml23.cpp"),
                encoding="utf-8").read().splitlines()
    mine = open(os.path.join(ROOT, "board_package/board_gate9_full_chain_rml23.cpp"),
                encoding="utf-8").read().splitlines()
    diff = list(difflib.unified_diff(base, mine, "base", "mine", lineterm=""))
    removed = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---")]
    added = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
    hunk_count = sum(1 for l in diff if l.startswith("@@"))
    added_text = "\n".join(added)
    removed_text = "\n".join(removed)
    bad = []
    if hunk_count != 4:
        bad.append("expected 4 hunks, got %d" % hunk_count)
    if removed != ['                    "radioml-original-npu-ab-24class-bf16-fix10)");']:
        bad.append("unexpected removed lines: %r" % (removed,))
    for marker in ('#include "radioml_singlesdr_ab_runner.hpp"',
                   "int run_radioml_original_singlesdr_ab(",
                   'phase == "radioml-original-singlesdr-ab-24class-bf16-fix10"',
                   '"radioml-original-singlesdr-ab-24class-bf16-fix10)"',
                   "emit_frame_rml24", "final_gate_pass", "device_not_found"):
        if marker not in added_text:
            bad.append("missing added marker: %s" % marker)
    if bad:
        _fail("board_gate9 red-line audit", bad)
    print("board_gate9_full_chain_rml23.cpp red-line audit: OK "
          "(4 hunks: include + wrapper + error-text + dispatch; 1 line removed)")


def audit_include_closure():
    bad = []
    for rel in RUNNER_BASE_HEADERS:
        if not os.path.exists(os.path.join(BASE_DIR, rel.replace("/", os.sep))):
            bad.append(rel + " (missing in base)")
    if bad:
        _fail("include-closure audit", bad)
    print("include-closure audit: OK (%d production headers present in base)"
          % len(RUNNER_BASE_HEADERS))


def audit_no_red_line_headers():
    # My change set must not contain ANY of the production recovery/runner headers.
    redline = ("iq_rf_training_frame", "iq_digital_loopback.hpp", "iq_dual_sdr",
               "iq_rf_sync_recovery", "iq_rf_loopback", "rml24_bf16_baseline",
               "rml24_raw.hpp", "iq_fix10_canonical_frame", "chain_common.hpp",
               "npu_classifier24.hpp", "board_common.hpp", "rf_fix_helpers.hpp",
               "iq_rf_per_frame_recovery", "iq_rf_frame_layout",
               "iq_pc_tx_board_rx", "iq_clean_iq_24class")
    bad = []
    for rel in EXPECTED_PATCH_FILES:
        if not rel.endswith((".hpp", ".cpp")):
            continue
        base = os.path.basename(rel)
        for rl in redline:
            if base == rl or base == rl + ".hpp" or base == rl + ".cpp":
                bad.append(rel + " is a red-line header")
    if bad:
        _fail("no-red-line-header audit", bad)
    print("no-red-line-header audit: OK (change set adds only 2 new board headers)")


def build_inputs_package():
    """Package the dualsdr-exported TX payload into the board's --input-dir data package.

    Re-verifies the 480 .i16 files against the dualsdr fork's SHA256SUMS.txt (the payload
    authority), then re-packages them VERBATIM with tx_manifest.tsv + a fresh per-file
    SHA256SUMS.txt into one deterministic gzip tar (npu-ab1 *_inputs.tar.gz convention).
    The TX-derived conversion rules are NEVER re-derived here.
    """
    tx = os.path.join(DUALSDR_DIR, "results", "tx_payload")
    if not os.path.isdir(tx):
        sys.exit("missing dualsdr tx_payload dir: %s" % tx)

    i16 = sorted(f for f in os.listdir(tx) if f.endswith(".i16"))
    if len(i16) != 480:
        sys.exit("expected 480 .i16 files in %s, found %d" % (tx, len(i16)))

    manifest = os.path.join(tx, "tx_manifest.tsv")
    if not os.path.isfile(manifest):
        sys.exit("missing tx_manifest.tsv in %s" % tx)
    with open(manifest, encoding="utf-8") as f:
        manifest_lines = f.read().rstrip("\n").split("\n")
    if len(manifest_lines) != 481:
        sys.exit("expected tx_manifest.tsv to have 481 lines (1 header + 480 data), got %d"
                 % len(manifest_lines))

    # Re-verify every .i16 against the dualsdr authority (SHA256SUMS.txt).
    dual_sums = os.path.join(tx, "SHA256SUMS.txt")
    if not os.path.isfile(dual_sums):
        sys.exit("missing dualsdr SHA256SUMS.txt (payload authority) in %s" % tx)
    dual = {}
    for line in open(dual_sums, encoding="utf-8"):
        parts = line.split()
        if len(parts) >= 2:
            dual[parts[1]] = parts[0]
    for n in i16:
        if n not in dual or dual[n] != sha256_of(os.path.join(tx, n)):
            sys.exit("tx_payload %s does not match dualsdr SHA256SUMS.txt" % n)

    work = tempfile.mkdtemp(prefix="pkg_singlesdr_ab1_input_")
    try:
        stage = os.path.join(work, INPUTS_NAME)
        os.makedirs(stage, exist_ok=True)
        for n in i16:
            shutil.copy2(os.path.join(tx, n), os.path.join(stage, n))
        shutil.copy2(manifest, os.path.join(stage, "tx_manifest.tsv"))
        n = write_sums(stage, INPUTS_SUMS_NAME)
        tar_path = os.path.join(DIST, INPUTS_NAME + ".tar.gz")
        build_tar_deterministic(stage, tar_path)
        print("determinism: OK (inputs tarball built twice, byte-identical)")
        shutil.copy2(os.path.join(stage, INPUTS_SUMS_NAME),
                     os.path.join(DIST, INPUTS_NAME + "_SHA256SUMS.txt"))
        print("== self-check ==")
        ok, total, good = verify_tar_flat(tar_path, INPUTS_SUMS_NAME)
        print("  %-48s files=%d ok=%d %s" % ("original-radioml-singlesdr-ab1 inputs",
                                              total, good, "PASS" if ok else "FAIL"))
        if not ok:
            sys.exit(1)
        print("  %-40s %d content-files  sha256=%s" %
              ("original-radioml-singlesdr-ab1 inputs", n, sha256_of(tar_path)))
        print("  %s" % tar_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    if not os.path.isdir(BASE_DIR):
        sys.exit("missing base tree: %s" % BASE_DIR)
    if not os.path.isdir(DUALSDR_DIR):
        sys.exit("missing dualsdr fork: %s" % DUALSDR_DIR)

    audit_change_set()
    audit_vendored_verbatim()
    audit_changed_files()
    audit_include_closure()
    audit_no_red_line_headers()

    os.makedirs(DIST, exist_ok=True)
    work = tempfile.mkdtemp(prefix="pkg_singlesdr_ab1_")
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

        print("== self-check ==")
        ok, total, good = verify_tar_flat(tar_path, PATCH_SUMS_NAME)
        print("  %-48s files=%d ok=%d %s" % ("original-radioml-singlesdr-ab1 patch",
                                              total, good, "PASS" if ok else "FAIL"))
        if not ok:
            sys.exit(1)

        print("== summary ==")
        print("  base npu-ab1 tree         %s" % BASE_DIR)
        print("  %-40s %d content-files  sha256=%s" %
              ("original-radioml-singlesdr-ab1 patch", n, sha256_of(tar_path)))
        print("  %s" % tar_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    build_inputs_package()


if __name__ == "__main__":
    main()
