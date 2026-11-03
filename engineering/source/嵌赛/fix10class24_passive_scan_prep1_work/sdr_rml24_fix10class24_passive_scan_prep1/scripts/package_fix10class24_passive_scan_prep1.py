#!/usr/bin/env python3
"""Package the fix10class24-passive-scan-prep1 board-test delivery (offline, PATCH only).

Sits on top of the deployed board state, which is FOUR frozen layers:
    dist/sdr_rml24_fix10class24_bf16_dualsdr2_rxrecovery1_full.tar.gz   (sha256 6fd93f78…)
  + dist/sdr_rml24_fix10class24_bf16_singlesdr_ab1_patch.tar.gz         (sha256 82e1aa8d…)
  + dist/sdr_rml24_fix10class24_bf16_scalarwl_4way_patch.tar.gz         (sha256 e4e6cf9d…)
  + dist/sdr_rml24_fix10class24_bf16_tx_rms_sweep1_patch.tar.gz         (sha256 bb69b0e2…)

This passive-scan-prep1 delivery is PURELY ADDITIVE on top of all four (deletions empty).
It adds the receive-only passive frequency-scan state machine + energy detector +
classification-contract gate (board_package/passive_scan.hpp), a host test, a synthetic
demo generator + its two example artifacts, and board-test docs.  It modifies NO existing
board_package header and NO runner: the feature is header-only and injectable, so the board
producer (a later integration step, NOT this task) backs ScanDeviceControl with pluto::Device.

    new:  board_package/passive_scan.hpp
    new:  host_tests/test_passive_scan.cpp
    new:  host_tests/make_passive_scan_demo.cpp
    chg:  host_tests/build_host_tests.sh      (register the new test + generator)
    chg:  host_tests/run_tests.sh             (register the new test)
    new:  docs/reuse_and_gap_review.md
    new:  docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_BOARDTEST.md
    new:  docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_AUDIT.md
    new:  docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_DEMO_RECORDS.tsv   (SYNTHETIC)
    new:  docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_RESULT_LIST.md     (SYNTHETIC)
    new:  scripts/package_fix10class24_passive_scan_prep1.py (this packager)

Red lines stay byte-identical to the deployed base: the recovery/runner headers, the 24-class
BF16 model json/raw + baselines + frozen assets, the 0.100 fidelity gate, the canonical 3 CI16
components, and the TX -40 dB safety ceiling.  The classification gate FAILS CLOSED to
CLASSIFICATION_UNAVAILABLE for a passive signal; an optional raw argmax is only ever an
explicitly-marked UNVERIFIED candidate, never a reliable identification.

Run with:
    python3 -I scripts/package_fix10class24_passive_scan_prep1.py
"""

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

# ---- four frozen base layers (the deployed board state) --------------------
BASE_FULL_TAR = os.path.abspath(os.path.join(
    ROOT, os.pardir, os.pardir,
    "fix10class24_dualsdr_rxrecovery1_work",
    "sdr_rml24_fix10class24_dualsdr_rxrecovery1",
    "dist", "sdr_rml24_fix10class24_bf16_dualsdr2_rxrecovery1_full.tar.gz"))

BASE_PATCH_TAR = os.path.abspath(os.path.join(
    ROOT, os.pardir, os.pardir,
    "fix10class24_singlesdr_ab1_work",
    "sdr_rml24_fix10class24_singlesdr_ab1",
    "dist", "sdr_rml24_fix10class24_bf16_singlesdr_ab1_patch.tar.gz"))

BASE_PATCH2_TAR = os.path.abspath(os.path.join(
    ROOT, os.pardir, os.pardir,
    "fix10class24_scalarwl_4way_work",
    "sdr_rml24_fix10class24_scalarwl_4way",
    "dist", "sdr_rml24_fix10class24_bf16_scalarwl_4way_patch.tar.gz"))

BASE_PATCH3_TAR = os.path.abspath(os.path.join(
    ROOT, os.pardir, os.pardir,
    "fix10class24_tx_rms_sweep1_work",
    "sdr_rml24_fix10class24_tx_rms_sweep1",
    "dist", "sdr_rml24_fix10class24_bf16_tx_rms_sweep1_patch.tar.gz"))

# Unique file each patch layer must contribute after overlay (fail-closed).
BASE_PATCH_REQUIRED = "board_package/iq_rf_loopback_transfer_24class_bf16_fix10.hpp"
BASE_PATCH2_REQUIRED = "board_package/iq_rf_loopback_24class_bf16_scalarwl_core.hpp"
BASE_PATCH3_REQUIRED = "scripts/run_fix10class24_tx_rms_sweep1.sh"

BASE_TOP = "sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2"

PATCH_NAME = "sdr_rml24_fix10class24_passive_scan_prep1_patch"
PATCH_SUMS_NAME = "FIX10CLASS24_PASSIVE_SCAN_PREP1_PATCH_SHA256SUMS.txt"

DELETE_LIST = []

# The exact change set this delivery must produce (new + changed).  Anything else in
# the full tree that differs from the base is a packaging error (fail-closed).
EXPECTED_PATCH_FILES = (
    "board_package/passive_scan.hpp",
    "docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_AUDIT.md",
    "docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_BOARDTEST.md",
    "docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_DEMO_RECORDS.tsv",
    "docs/M29_RML24_FIX10CLASS24_PASSIVE_SCAN_PREP1_RESULT_LIST.md",
    "docs/reuse_and_gap_review.md",
    "host_tests/build_host_tests.sh",
    "host_tests/make_passive_scan_demo.cpp",
    "host_tests/run_tests.sh",
    "host_tests/test_passive_scan.cpp",
    "scripts/package_fix10class24_passive_scan_prep1.py",
)

EXCLUDED_DIRS = {"host_tests/bin", "host_tests/__pycache__", "host_tools/__pycache__",
                 "scripts/__pycache__", "dist", ".git",
                 "host_tools/.build_burst_cache", "host_tools/.replay24_cache",
                 "host_tools/.force_classify_cache", ".pytest_cache",
                 "results", "clean24_smoke/hardopLog"}

EXCLUDED_FILES = {
    "host_tests/build_host_tests.log",
    "host_tests/run_tests.log",
}

# Derived sums artifacts of prior layers; never enter the passive-scan change set.
ROOT_SUMS_NAME = "SHA256SUMS.txt"
BASE_PATCH_SUMS_NAME = "FIX10CLASS24_SINGLESDR_AB1_PATCH_SHA256SUMS.txt"
BASE_PATCH2_SUMS_NAME = "FIX10CLASS24_SCALARWL_4WAY_PATCH_SHA256SUMS.txt"
BASE_PATCH3_SUMS_NAME = "FIX10CLASS24_TX_RMS_SWEEP1_PATCH_SHA256SUMS.txt"

PROTECTED_DIRS = ("model_rml23/", "model_12class/", "deployment_golden/",
                  "model_rml24_bf16/", "baselines/", "clean24_smoke/",
                  "contracts/")

RED_LINE_HEADERS = (
    "board_package/iq_rf_training_frame.hpp",
    "board_package/iq_digital_loopback.hpp",
    "board_package/iq_pc_tx_board_rx_transfer_fix10.hpp",
    "board_package/iq_rf_fix9r_baseline.hpp",
    "board_package/iq_clean_baseline.hpp",
    "board_package/iq_dual_sdr_coarse_cfo_recovery.hpp",
    "board_package/iq_pc_tx_board_rx_23class_fix10.hpp",
    "board_package/iq_fix10_canonical_frame.hpp",
    "board_package/iq_fix10_canonical_frame_data.hpp",
    "board_package/rml23_merged.hpp",
    "board_package/rml24_raw.hpp",
    "board_package/rml24_bf16_baseline.hpp",
    "board_package/iq_clean_iq_24class_bf16_fix10.hpp",
    "board_package/iq_rf_sync_recovery.hpp",
    "board_package/iq_pc_tx_board_rx_24class_bf16_fix10.hpp",
    "board_package/iq_rf_loopback_transfer_24class_bf16_fix10.hpp",
    "board_package/iq_rf_loopback_24class_bf16_fix10.hpp",
)

RED_LINE_CONTRACTS = (
    "contracts/rml23_merged_contract.py",
    "contracts/rml23_merged_contract.json",
    "contracts/rml24_raw_contract.py",
)

CANONICAL_COMPONENTS = (
    "contracts/fix10_canonical_frame_v1/preamble.ci16",
    "contracts/fix10_canonical_frame_v1/payload_training.ci16",
    "contracts/fix10_canonical_frame_v1/tail.ci16",
    "contracts/fix10_canonical_frame_v1/manifest.tsv",
    "contracts/fix10_canonical_frame_v1/SHA256SUMS.txt",
)

_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"')
_CPP_EXT = (".cpp", ".hpp", ".h", ".cc", ".cxx")
_INCLUDE_DIRS = ("board_package", "sdr_adapter", "ui_sw")


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_bytes(path, data, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    os.chmod(path, mode)


def list_files(stage):
    out = []
    for dirpath, dirnames, filenames in os.walk(stage):
        dirnames[:] = sorted(
            d for d in dirnames
            if os.path.relpath(os.path.join(dirpath, d), stage).replace(os.sep, "/")
            not in EXCLUDED_DIRS)
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), stage).replace(os.sep, "/")
            if rel not in EXCLUDED_FILES and rel != ROOT_SUMS_NAME \
                    and rel != BASE_PATCH_SUMS_NAME and rel != BASE_PATCH2_SUMS_NAME \
                    and rel != BASE_PATCH3_SUMS_NAME:
                out.append(rel)
    return sorted(out)


def write_sums(stage, sums_name):
    rels = [r for r in list_files(stage) if r != sums_name]
    lines = ["%s *%s\n" % (sha256_of(os.path.join(stage, rel.replace("/", os.sep))), rel)
             for rel in rels]
    write_bytes(os.path.join(stage, sums_name), "".join(sorted(lines)).encode("utf-8"))
    return len(rels)


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


def build_tar_deterministic(make_fn, stage, tar_path):
    r1 = tar_path + ".run1"
    r2 = tar_path + ".run2"
    make_fn(stage, r1)
    make_fn(stage, r2)
    with open(r1, "rb") as a, open(r2, "rb") as b:
        if a.read() != b.read():
            sys.exit("DETERMINISM FAILED: %s" % tar_path)
    os.remove(r2)
    os.replace(r1, tar_path)


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


def _cpp_includes(text):
    out = []
    for line in text.splitlines():
        m = _INCLUDE_RE.match(line)
        if m:
            out.append(m.group(1))
    return out


def audit_dependency_closure(full_dir, files, extra_roots=()):
    roots = (full_dir,) + tuple(extra_roots)
    by_base = {}
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(
                d for d in dirnames
                if os.path.relpath(os.path.join(dirpath, d), root).replace(os.sep, "/")
                not in EXCLUDED_DIRS)
            for name in filenames:
                if name.endswith(_CPP_EXT):
                    p = os.path.join(dirpath, name)
                    by_base.setdefault(name, []).append(p)
    missing = set()
    for rel in files:
        if not rel.endswith(_CPP_EXT):
            continue
        abs_path = os.path.join(full_dir, rel.replace("/", os.sep))
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            includes = _cpp_includes(f.read())
        for inc in includes:
            cands = [os.path.normpath(os.path.join(os.path.dirname(abs_path), inc))]
            for root in roots:
                cands += [os.path.normpath(os.path.join(root, d, inc))
                          for d in _INCLUDE_DIRS]
            if not any(os.path.exists(c) for c in cands):
                base = os.path.basename(inc)
                hits = by_base.get(base, [])
                if len(hits) != 1:
                    missing.add(rel + " -> " + inc)
    return sorted(missing)


def verify_byte_identical(full_dir, base_dir, rels, label):
    violations = []
    for rel in rels:
        ff = os.path.join(full_dir, rel.replace("/", os.sep))
        bf = os.path.join(base_dir, rel.replace("/", os.sep))
        if not os.path.exists(bf):
            violations.append(rel + " (missing in base)")
        elif not os.path.exists(ff) or sha256_of(ff) != sha256_of(bf):
            violations.append(rel + " (differs from base)")
    return sorted(violations)


def verify_protected_unchanged(full_dir, base_dir):
    violations = []
    for pdir in PROTECTED_DIRS:
        base_p = os.path.join(base_dir, pdir)
        full_p = os.path.join(full_dir, pdir)
        if not os.path.isdir(base_p):
            continue
        for dirpath, dirnames, filenames in os.walk(base_p):
            dirnames.sort()
            for name in sorted(filenames):
                bf = os.path.join(dirpath, name)
                rel = os.path.relpath(bf, base_dir).replace(os.sep, "/")
                ff = os.path.join(full_dir, rel.replace("/", os.sep))
                if not os.path.exists(ff) or sha256_of(ff) != sha256_of(bf):
                    violations.append(rel)
    return sorted(violations)


def derive_change_set(full_dir, base_dir):
    base = {rel: sha256_of(os.path.join(base_dir, rel.replace("/", os.sep)))
            for rel in list_files(base_dir)}
    tree = {rel: sha256_of(os.path.join(full_dir, rel.replace("/", os.sep)))
            for rel in list_files(full_dir)}
    base_keys = set(base)
    tree_keys = set(tree)
    new = sorted(tree_keys - base_keys)
    deleted = sorted(base_keys - tree_keys)
    changed = sorted(k for k in (tree_keys & base_keys) if tree[k] != base[k])
    return new, changed, deleted


def audit_complete_delta(full_dir, base_dir, patch_files):
    patch_set = set(patch_files)
    violations = []
    for rel in list_files(full_dir):
        bf = os.path.join(base_dir, rel.replace("/", os.sep))
        ff = os.path.join(full_dir, rel.replace("/", os.sep))
        if os.path.exists(bf) and sha256_of(ff) == sha256_of(bf):
            continue
        if rel in patch_set:
            continue
        violations.append("in full but not in base and not in patch: " + rel)
    for rel in list_files(base_dir):
        bf = os.path.join(base_dir, rel.replace("/", os.sep))
        ff = os.path.join(full_dir, rel.replace("/", os.sep))
        if os.path.exists(ff) and sha256_of(ff) == sha256_of(bf):
            continue
        if rel in patch_set:
            continue
        violations.append("in base but not in full and not in patch: " + rel)
    return sorted(violations)


def verify_patch_overlay(base_dir, patch_dir, full_dir, patch_files):
    over = os.path.join(os.path.dirname(full_dir), "_overlay")
    shutil.copytree(base_dir, over)
    for rel in DELETE_LIST:
        p = os.path.join(over, rel.replace("/", os.sep))
        if os.path.exists(p):
            os.remove(p)
    for rel in patch_files:
        src = os.path.join(patch_dir, rel.replace("/", os.sep))
        dst = os.path.join(over, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    full_rels = set(list_files(full_dir))
    over_rels = set(list_files(over))
    viol = []
    if full_rels != over_rels:
        viol.append("file-set mismatch: only-full=%s only-overlay=%s" %
                    (sorted(full_rels - over_rels), sorted(over_rels - full_rels)))
    for rel in sorted(full_rels & over_rels):
        if sha256_of(os.path.join(full_dir, rel)) != sha256_of(os.path.join(over, rel)):
            viol.append(rel)
    return viol


def _fail(label, violations):
    print(label + " FAILED:", file=sys.stderr)
    for v in violations:
        print("  " + v, file=sys.stderr)
    sys.exit(1)


def main():
    for t in (BASE_FULL_TAR, BASE_PATCH_TAR, BASE_PATCH2_TAR, BASE_PATCH3_TAR):
        if not os.path.exists(t):
            sys.exit("missing base layer: %s" % t)

    work = tempfile.mkdtemp(prefix="pkg_fix10class24_passive_scan_prep1_")
    try:
        # ---- base = rxrecovery1 FULL + singlesdr + scalarwl + tx-rms-sweep1 ----
        base_x = os.path.join(work, "base")
        os.makedirs(base_x)
        with tarfile.open(BASE_FULL_TAR, "r:gz") as t:
            t.extractall(base_x, filter="data")
        base_ref = os.path.join(base_x, BASE_TOP)
        if not os.path.isdir(base_ref):
            sys.exit("rxrecovery1 base missing top dir: %s" % BASE_TOP)
        with tarfile.open(BASE_PATCH_TAR, "r:gz") as t:
            t.extractall(base_ref, filter="data")
        if not os.path.isfile(os.path.join(base_ref, BASE_PATCH_REQUIRED)):
            sys.exit("singlesdr-ab1 overlay missing: %s" % BASE_PATCH_REQUIRED)
        with tarfile.open(BASE_PATCH2_TAR, "r:gz") as t:
            t.extractall(base_ref, filter="data")
        if not os.path.isfile(os.path.join(base_ref, BASE_PATCH2_REQUIRED)):
            sys.exit("scalarwl-4way overlay missing: %s" % BASE_PATCH2_REQUIRED)
        with tarfile.open(BASE_PATCH3_TAR, "r:gz") as t:
            t.extractall(base_ref, filter="data")
        if not os.path.isfile(os.path.join(base_ref, BASE_PATCH3_REQUIRED)):
            sys.exit("tx-rms-sweep1 overlay missing: %s" % BASE_PATCH3_REQUIRED)
        print("base overlay: OK (rxrecovery1 FULL + singlesdr-ab1 PATCH + "
              "scalarwl-4way PATCH + tx-rms-sweep1 PATCH)")

        # ---- full staging (current tree, minus derived sums) ----
        full = os.path.join(work, "full", BASE_TOP)
        os.makedirs(full, exist_ok=True)
        for rel in list_files(ROOT):
            src = os.path.join(ROOT, rel.replace("/", os.sep))
            dst = os.path.join(full, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

        # ---- derive + verify the change set ----
        new, changed, deleted = derive_change_set(full, base_ref)
        if sorted(deleted) != sorted(DELETE_LIST):
            _fail("delete-list audit", [
                "expected deletions=%s" % sorted(DELETE_LIST),
                "actual deletions=%s" % sorted(deleted)])
        PATCH_FILES = sorted(new + changed)
        exp = sorted(EXPECTED_PATCH_FILES)
        if PATCH_FILES != exp:
            _fail("change-set audit", [
                "expected %d files=%s" % (len(exp), exp),
                "actual   %d files=%s" % (len(PATCH_FILES), PATCH_FILES)])
        print("change-set audit: OK (%d new + %d changed = %d patch files, exactly as "
              "expected)" % (len(new), len(changed), len(PATCH_FILES)))
        for rel in sorted(new):
            print("  new    : %s" % rel)
        for rel in sorted(changed):
            print("  changed: %s" % rel)

        # ---- audits ----
        v = verify_byte_identical(full, base_ref, RED_LINE_HEADERS, "red-line")
        if v:
            _fail("red-line header audit", v)
        print("red-line header audit: OK (%d headers byte-identical to deployed base)"
              % len(RED_LINE_HEADERS))

        v = verify_byte_identical(full, base_ref, RED_LINE_CONTRACTS, "red-line-contract")
        if v:
            _fail("red-line contract audit", v)
        print("red-line contract audit: OK (merged + raw24 contracts byte-identical)")

        v = verify_protected_unchanged(full, base_ref)
        if v:
            _fail("protected-dir audit", v)
        print("protected-dir audit: OK (model/weights/labels/preprocess/frozen assets "
              "byte-identical)")

        v = verify_byte_identical(full, base_ref, CANONICAL_COMPONENTS, "canonical")
        if v:
            _fail("canonical-component audit", v)
        print("canonical-component audit: OK (3 CI16 + manifest byte-identical)")

        v = audit_dependency_closure(full, files=PATCH_FILES)
        if v:
            _fail("dependency-closure audit", v)
        print("dependency-closure audit: OK")

        v = audit_complete_delta(full, base_ref, PATCH_FILES)
        if v:
            _fail("complete-delta audit", v)
        print("complete-delta audit: OK (base + patch == full tree)")

        # ---- patch staging (flat) ----
        p = os.path.join(work, "patch")
        for rel in PATCH_FILES:
            src = os.path.join(ROOT, rel.replace("/", os.sep))
            write_bytes(os.path.join(p, rel.replace("/", os.sep)),
                        open(src, "rb").read())

        v = audit_dependency_closure(p, files=PATCH_FILES, extra_roots=(base_ref,))
        if v:
            _fail("patch self-containment audit", v)
        print("patch self-containment audit: OK (patch overlays onto deployed base alone)")

        v = verify_patch_overlay(base_ref, p, full, PATCH_FILES)
        if v:
            _fail("patch-over-base overlay audit", v)
        print("patch-over-base overlay audit: OK (literal byte-level == full)")

        # ---- sums + tarball (PATCH only) ----
        p_n = write_sums(p, PATCH_SUMS_NAME)

        os.makedirs(DIST, exist_ok=True)
        patch_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        build_tar_deterministic(make_tar_flat, p, patch_tar)
        print("determinism: OK (patch tarball built twice, byte-identical)")

        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME),
                     os.path.join(DIST, PATCH_NAME + "_SHA256SUMS.txt"))

        # ---- self-check (independent unpack + sha256sum -c) ----
        print("== self-check ==")
        ok, total, good = verify_tar_flat(patch_tar, PATCH_SUMS_NAME)
        print("  %-30s files=%d ok=%d %s" % ("fix10class24 passive-scan-prep1 patch",
                                              total, good, "PASS" if ok else "FAIL"))
        if not ok:
            sys.exit(1)

        print("== summary ==")
        print("  base rxrecovery1 full      sha256=%s" % sha256_of(BASE_FULL_TAR))
        print("  base singlesdr-ab1 patch   sha256=%s" % sha256_of(BASE_PATCH_TAR))
        print("  base scalarwl-4way patch   sha256=%s" % sha256_of(BASE_PATCH2_TAR))
        print("  base tx-rms-sweep1 patch   sha256=%s" % sha256_of(BASE_PATCH3_TAR))
        print("  %-30s %d content-files  sha256=%s" %
              ("fix10class24 passive-scan-prep1 patch", p_n, sha256_of(patch_tar)))
        print("  %s" % patch_tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
