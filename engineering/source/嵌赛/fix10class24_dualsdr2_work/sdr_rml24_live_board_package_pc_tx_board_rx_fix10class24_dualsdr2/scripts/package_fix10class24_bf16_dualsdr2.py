#!/usr/bin/env python3
"""Package the fix10class24-dualsdr2 diagnostic delivery (offline, batch 1).

Sits on top of the frozen dualsdr1 24-class BF16 dual-SDR full package
(SHA 25659516..., the "READY-FOR-BOARD-TEST" delivery whose two-sample board
test FAILED in the RF recovery gate BEFORE NPU: BPSK payload_training_residual
~0.10-0.11 > 0.10).  This delivery carries ONLY the auditable recovery
diagnostic delta:

  * board_package/iq_fix10class24_failed_rx_dump.hpp   (failed-RX 7-file dump)
  * host_tools/replay_fix10class24_failed_rx.{hpp,cpp,sh} (offline replayer)
  * board_package/iq_pc_tx_board_rx_24class_bf16_fix10.hpp (--dump-failed-rx +
    --dump-recovery-diagnostics wiring, default byte-equivalent)
  * host_tests/test_fix10class24_failed_rx_dump.cpp / test_fix10class24_replay.cpp
  * host_tests/build_host_tests.sh / run_tests.sh (test wiring)
  * this audit doc + this packager.

The dual-SDR recovery core (iq_dual_sdr_coarse_cfo_recovery.hpp ->
iqrfrec::estimate/apply), the frame math, the transfer/provenance state machine,
the canonical frame, the 23-class merge, the frozen BF16 24-output model, the
raw24 contract, and the 24 clean IQ assets are all RED LINE and byte-identical
to the dualsdr1 base.  The ONLY 24-class runner touched is the dual-SDR runner
(which is the failing path being instrumented).

The patch is stored FLAT (files at tarball root) so overlaying it onto the
extracted dualsdr1 full tree reproduces the dualsdr2 full tree byte-for-byte.
The packager proves this with a literal byte-level overlay verification.

Fail-closed audits run BEFORE anything is emitted:
  * RED-LINE headers (14 recovery/frame/transfer/canonical/merge/raw24 headers)
    byte-identical to the dualsdr1 full base.
  * PROTECTED dirs (model_rml23/, model_12class/, deployment_golden/,
    model_rml24_bf16/, baselines/, clean24_smoke/, and existing contracts/)
    byte-identical to base.
  * canonical training components (3 CI16 + canonical headers) byte-identical.
  * derived change-set == audited change-set (no unexpected new/changed/deleted).
  * every quoted include of every patched C++ file resolves inside the tree.
  * complete-delta: base + patch == full tree (no deletions).
  * literal patch-over-base overlay == full (byte-level).
  * old-fix10 (external_rf / pluto_external) zero-residual.

Each tarball carries a SHA256SUMS in the repo's `HASH *relpath` convention.
stdlib only; deterministic (uid/gid 0, mtime 0, sorted entries, gzip level 9,
mtime 0), and every tarball is built TWICE and byte-compared.
Run with:
    python -I scripts/package_fix10class24_bf16_dualsdr2.py
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

# The frozen board-tested source the dualsdr2 diagnostic delta is defined
# against: the dualsdr1 24-class BF16 dual-SDR full package (whose two-sample
# board test FAILED at the RF recovery gate -- this delivery instruments it).
BASE_FULL_TAR = os.path.abspath(os.path.join(
    ROOT, os.pardir, os.pardir, "fix10class24_dualsdr1_work",
    "sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24", "dist",
    "sdr_rml24_fix10class24_bf16_dualsdr_boardtest_full.tar.gz"))

FULL_NAME = "sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2"
FULL_TAR_BASENAME = "sdr_rml24_fix10class24_bf16_dualsdr2_diag_full"
FULL_SUMS_NAME = "SHA256SUMS.txt"

PATCH_NAME = "sdr_rml24_fix10class24_bf16_dualsdr2_diag_patch"
PATCH_SUMS_NAME = "FIX10CLASS24_DUALSDR2_DIAG_PATCH_SHA256SUMS.txt"

# dualsdr2 drops nothing from the dualsdr1 base -- it is purely additive (the
# diagnostic headers/tools/tests) plus three in-place modifications.  There is
# no dualsdr1-internal artifact superseded by this delivery.
DELETE_LIST = []

# Directories never packaged (build products / python cache / output).
EXCLUDED_DIRS = {"host_tests/bin", "host_tests/__pycache__", "host_tools/__pycache__",
                 "scripts/__pycache__", "dist", ".git",
                 "host_tools/.build_burst_cache", "results"}

# Transient files never packaged (stale host-test logs from a manual run).
EXCLUDED_FILES = {
    "host_tests/build_host_tests.log",
    "host_tests/run_tests.log",
}

# Directories whose base contents must be byte-identical to the dualsdr1 base
# (model / weights / labels / preprocess / mapping / frozen 24-class assets).
PROTECTED_DIRS = ("model_rml23/", "model_12class/", "deployment_golden/",
                  "model_rml24_bf16/", "baselines/", "clean24_smoke/",
                  "contracts/")

# RED LINE: recovery core, frame math, transfer/provenance state machine,
# canonical-sync contract, 23-class merge, raw24 unmerged contract, and the
# 24-class clean-IQ NPU direct-inject runner (the path that PASSED digitally).
# The dualsdr2 tree must NOT touch any of them.  The ONLY 24-class runner this
# task may change is iq_pc_tx_board_rx_24class_bf16_fix10.hpp (dual-SDR), which
# is intentionally NOT in this list.
RED_LINE_HEADERS = (
    "board_package/iq_rf_sync_recovery.hpp",
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
)

# The 23-class merged contract and the raw24 unmerged contract stay identical.
RED_LINE_CONTRACTS = (
    "contracts/rml23_merged_contract.py",
    "contracts/rml23_merged_contract.json",
    "contracts/rml24_raw_contract.py",
)

# The canonical training components frozen from aarch64 output -- the cross-arch
# fix itself; must stay byte-identical to the dualsdr1 base.
CANONICAL_COMPONENTS = (
    "contracts/fix10_canonical_frame_v1/preamble.ci16",
    "contracts/fix10_canonical_frame_v1/payload_training.ci16",
    "contracts/fix10_canonical_frame_v1/tail.ci16",
    "contracts/fix10_canonical_frame_v1/manifest.tsv",
    "contracts/fix10_canonical_frame_v1/SHA256SUMS.txt",
)

_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"')
_CPP_EXT = (".cpp", ".hpp", ".h", ".cc", ".cxx")


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
            if rel not in EXCLUDED_FILES:
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


def make_tar(stage, tar_path):
    """Full-tree tarball: single top directory == tree basename."""
    top = os.path.basename(stage.rstrip("/\\"))
    raw = tar_path + ".tmp.tar"

    entries = [("", True)]
    for dirpath, dirnames, filenames in os.walk(stage):
        dirnames[:] = sorted(
            d for d in dirnames
            if os.path.relpath(os.path.join(dirpath, d), stage).replace(os.sep, "/")
            not in EXCLUDED_DIRS)
        filenames.sort()
        for d in dirnames:
            entries.append((os.path.relpath(os.path.join(dirpath, d), stage)
                            .replace(os.sep, "/"), True))
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), stage).replace(os.sep, "/")
            if rel not in EXCLUDED_FILES:
                entries.append((rel, False))
    entries.sort(key=lambda e: e[0])

    with tarfile.open(raw, "w", format=tarfile.GNU_FORMAT) as t:
        for rel, is_dir in entries:
            full = stage if rel == "" else os.path.join(stage, rel.replace("/", os.sep))
            arc = top if rel == "" else os.path.join(top, rel).replace(os.sep, "/")
            info = _entry_info(full, arc, is_dir)
            if is_dir:
                t.addfile(info)
            else:
                with open(full, "rb") as f:
                    t.addfile(info, f)
    _gzip(raw, tar_path)


def make_tar_flat(stage, tar_path):
    """Patch tarball: files at root (board_package/..., host_tests/...), no top
    dir, so `tar -xzf patch -C <extracted-full-top>` overlays directly."""
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
            sys.exit("DETERMINISM FAILED: %s (two builds differ)" % tar_path)
    os.remove(r2)
    os.replace(r1, tar_path)


def verify_tar(tar_path, sums_name, topdir):
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(tar_path, "r:gz") as t:
            t.extractall(td, filter="data")
        d = os.path.join(td, topdir)
        ok = 0
        bad = 0
        with open(os.path.join(d, sums_name), "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                hx, _, rel = line.partition(" *")
                p = os.path.join(d, rel.replace("/", os.sep))
                if sha256_of(p) == hx:
                    ok += 1
                else:
                    bad += 1
                    print("  MISMATCH: %s" % rel, file=sys.stderr)
        return (bad == 0, ok + bad, ok)


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
                p = os.path.join(td, rel.replace("/", os.sep))
                if sha256_of(p) == hx:
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


_INCLUDE_DIRS = ("board_package", "sdr_adapter", "ui_sw")


def audit_dependency_closure(full_dir, files, extra_roots=()):
    """Fail-closed: every quoted include of every audited C++ file must resolve to
    a real file inside `full_dir` (or one of `extra_roots`)."""
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
    """Derive the dualsdr2 diagnostic delta from a literal walk of both trees."""
    base = {rel: sha256_of(os.path.join(base_dir, rel.replace("/", os.sep)))
            for rel in list_files(base_dir) if rel != FULL_SUMS_NAME}
    tree = {rel: sha256_of(os.path.join(full_dir, rel.replace("/", os.sep)))
            for rel in list_files(full_dir) if rel != FULL_SUMS_NAME}
    base_keys = set(base)
    tree_keys = set(tree)
    new = sorted(tree_keys - base_keys)
    deleted = sorted(base_keys - tree_keys)
    changed = sorted(k for k in (tree_keys & base_keys) if tree[k] != base[k])
    return new, changed, deleted


def audit_complete_delta(full_dir, base_dir, patch_files):
    """Fail-closed: base + patch == full tree (no deletions), both directions."""
    patch_set = set(patch_files)
    violations = []
    for rel in list_files(full_dir):
        if rel == FULL_SUMS_NAME:
            continue
        bf = os.path.join(base_dir, rel.replace("/", os.sep))
        ff = os.path.join(full_dir, rel.replace("/", os.sep))
        if os.path.exists(bf) and sha256_of(ff) == sha256_of(bf):
            continue
        if rel in patch_set:
            continue
        violations.append("in full but not in base and not in patch: " + rel)
    for rel in list_files(base_dir):
        if rel == FULL_SUMS_NAME:
            continue
        bf = os.path.join(base_dir, rel.replace("/", os.sep))
        ff = os.path.join(full_dir, rel.replace("/", os.sep))
        if os.path.exists(ff) and sha256_of(ff) == sha256_of(bf):
            continue
        if rel in patch_set:
            continue
        violations.append("in base but not in full and not in patch: " + rel)
    return sorted(violations)


def verify_patch_overlay(base_dir, patch_dir, full_dir, patch_files):
    """Literal byte-level proof that overlaying the patch onto the dualsdr1 full
    base reproduces the dualsdr2 full tree."""
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

    full_rels = set(r for r in list_files(full_dir) if r != FULL_SUMS_NAME)
    over_rels = set(r for r in list_files(over) if r != FULL_SUMS_NAME)
    viol = []
    if full_rels != over_rels:
        viol.append("file-set mismatch: only-full=%s only-overlay=%s" %
                    (sorted(full_rels - over_rels), sorted(over_rels - full_rels)))
    for rel in sorted(full_rels & over_rels):
        if sha256_of(os.path.join(full_dir, rel)) != \
           sha256_of(os.path.join(over, rel)):
            viol.append(rel)
    return viol


def _fail(label, violations):
    print(label + " FAILED:", file=sys.stderr)
    for v in violations:
        print("  " + v, file=sys.stderr)
    sys.exit(1)


def main():
    if not os.path.exists(BASE_FULL_TAR):
        sys.exit("missing dualsdr1 full base: %s" % BASE_FULL_TAR)

    work = tempfile.mkdtemp(prefix="pkg_fix10class24_dualsdr2_")
    try:
        # ---- base = extracted dualsdr1 full (frozen 24-class board-tested source) ----
        base_x = os.path.join(work, "base")
        os.makedirs(base_x)
        with tarfile.open(BASE_FULL_TAR, "r:gz") as t:
            t.extractall(base_x, filter="data")
        base_ref = os.path.join(base_x,
                                "sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24")
        if not os.path.isdir(base_ref):
            sys.exit("dualsdr1 base missing top dir")

        # ---- full staging (current tree, minus derived root sums) ----
        full = os.path.join(work, "full", FULL_NAME)
        os.makedirs(full, exist_ok=True)
        for rel in list_files(ROOT):
            if rel == FULL_SUMS_NAME:
                continue
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
        print("delete-list audit: OK (no files dropped from the dualsdr1 base)")
        PATCH_FILES = sorted(new + changed)
        if not PATCH_FILES:
            sys.exit("empty change set")
        print("change-set audit: OK (%d new + %d changed = %d patch files)"
              % (len(new), len(changed), len(PATCH_FILES)))

        # ---- audits ----
        v = verify_byte_identical(full, base_ref, RED_LINE_HEADERS, "red-line")
        if v:
            _fail("red-line header audit", v)
        print("red-line header audit: OK (%d headers byte-identical to dualsdr1)"
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
        print("canonical-component audit: OK (3 CI16 + manifest byte-identical to base)")

        v = audit_dependency_closure(full, files=PATCH_FILES)
        if v:
            _fail("dependency-closure audit", v)
        print("dependency-closure audit: OK")

        v = audit_complete_delta(full, base_ref, PATCH_FILES)
        if v:
            _fail("complete-delta audit", v)
        print("complete-delta audit: OK (base + patch == full tree)")

        for rel in list_files(full):
            if "external_rf" in rel or "pluto_external" in rel:
                _fail("old-fix10 zero-residual", [rel + " leaked"])
        print("old-fix10 zero-residual: OK")

        # ---- patch staging (flat) ----
        p = os.path.join(work, "patch")
        for rel in PATCH_FILES:
            src = os.path.join(ROOT, rel.replace("/", os.sep))
            write_bytes(os.path.join(p, rel.replace("/", os.sep)),
                        open(src, "rb").read())

        v = audit_dependency_closure(p, files=PATCH_FILES, extra_roots=(base_ref,))
        if v:
            _fail("patch self-containment audit", v)
        print("patch self-containment audit: OK (patch overlays onto dualsdr1 alone)")

        v = verify_patch_overlay(base_ref, p, full, PATCH_FILES)
        if v:
            _fail("patch-over-base overlay audit", v)
        print("patch-over-base overlay audit: OK (literal byte-level == full)")

        # ---- sums + tarballs ----
        p_n = write_sums(p, PATCH_SUMS_NAME)
        full_n = write_sums(full, FULL_SUMS_NAME)

        os.makedirs(DIST, exist_ok=True)
        patch_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        full_tar = os.path.join(DIST, FULL_TAR_BASENAME + ".tar.gz")
        build_tar_deterministic(make_tar_flat, p, patch_tar)
        build_tar_deterministic(make_tar, full, full_tar)
        print("determinism: OK (each tarball built twice, byte-identical)")

        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME),
                     os.path.join(DIST, PATCH_NAME + "_SHA256SUMS.txt"))
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_TAR_BASENAME + "_SHA256SUMS.txt"))

        # ---- self-check (independent unpack + sha256sum -c) ----
        print("== self-check ==")
        ok, total, good = verify_tar_flat(patch_tar, PATCH_SUMS_NAME)
        print("  %-30s files=%d ok=%d %s" % ("fix10class24 dualsdr2 patch", total, good,
                                              "PASS" if ok else "FAIL"))
        if not ok:
            sys.exit(1)
        ok, total, good = verify_tar(full_tar, FULL_SUMS_NAME, FULL_NAME)
        print("  %-30s files=%d ok=%d %s" % ("fix10class24 dualsdr2 full", total, good,
                                              "PASS" if ok else "FAIL"))
        if not ok:
            sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix10class24 dualsdr2 patch", patch_tar, p_n),
            ("fix10class24 dualsdr2 full", full_tar, full_n),
        ]:
            print("  %-30s %d content-files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
