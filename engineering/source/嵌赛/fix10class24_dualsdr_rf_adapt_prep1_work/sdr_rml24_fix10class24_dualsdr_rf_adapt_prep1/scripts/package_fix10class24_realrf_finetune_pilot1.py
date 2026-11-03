#!/usr/bin/env python3
"""Package the fix10class24 REALRF-FINETUNE-PILOT1 board-test delivery (offline, PATCH).

M29-RML24-REALRF-FINETUNE-PILOT1 adds ONE board phase:
    iq-pc-tx-board-rx-24class-finetune-pilot1
= the REAL dual-SDR capture runner that records the 960-frame finetune-pilot training
set (4 sessions x 24 classes x 10 source waveforms).  PC owns the TX SDR (plays the
frozen TX payloads over coax), board owns the RX SDR (capture -> CFO/sync/gain recovery
-> D2 restore -> save-before-gate export of 32-field result TSV + raw_rx/model_input/
logits).  Judgement (finetune-promising vs no-generalization) is done OFFLINE by
line_c/scripts/judge_realrf_pilot.py -- NEVER here.

Sits on top of the deployed board state = rxrecovery1 FULL + singlesdr-ab1 PATCH +
scalarwl-4way PATCH + rf-adapt-prep1 PATCH (the 4-tar base chain below).  Purely
ADDITIVE (deletions empty) + in-place wiring edits:

  * board_package/pilot1_capture_schema.hpp     (new: 32-field result schema, iCraft/
    libiio-free -- the contract shared with line_c judge_realrf_pilot.py)
  * board_package/pilot1_tx_manifest.hpp        (new: 3-field board-public TX-manifest
    loader, fail-closed, iCraft/libiio-free -- session_id/source_id/tx_payload_sha256,
    no class truth)
  * board_package/pilot1_capture_runner.hpp     (new: board-only capture runner --
    save-before-gate export, no judgement, no 0.100 gate bypass; truth columns left
    empty -- review 39e5 Blocker 2)
  * host_tools/pilot1_tx_manifest.py            (new: Windows 3-col identity + 5-col
    payload manifest loader)
  * host_tools/pc_tx_radioml_dualsdr.py         (new: PC TX SDR service, plays the
    frozen payloads over coax; TCP control + identity only)
  * host_tools/fix10_tx_protocol.py             (modified: pilot1 fixed public scale
    accepts exactly target_rms=0; legacy input kinds remain strictly positive)
  * host_tests/test_pilot1_capture.cpp          (new: fail-closed host test)
  * host_tests/test_pc_tx_protocol_fix10.py     (modified: fixed-scale/legacy and
    non-finite target-RMS counterexamples)
  * host_tests/pilot1_e2e_sim.cpp               (new: 24-frame end-to-end sim -- one
    frame per class, deterministic, cross-checks schema + save-before-gate)
  * host_tests/pilot1_capture_runner_syntax.cpp (new: full-runner -fsyntax-only TU --
    review 39e5 Blocker 1, catches use-before-declaration before any board build)
  * scripts/run_pilot1_capture.sh               (new: board run script)
  * board_package/gate9_phase.hpp + board_package/board_gate9_full_chain_rml23.cpp
    (additive phase wiring for iq-pc-tx-board-rx-24class-finetune-pilot1; 4-point
    dispatch)
  * host_tests/build_host_tests.sh + host_tests/run_tests.sh + host_tests/syntax_check.sh
    (host-test wiring; syntax_check runs the full runner TU)
  * this packager.

The 0.10 payload_training_residual gate, the production recovery core
(iq_rf_sync_recovery.hpp + iq_dual_sdr_coarse_cfo_recovery.hpp), the dual-SDR runner,
the canonical frame, the wide-linear header, the scalarwl-4way core + runner, the
raw24/baseline contracts, the 24-class BF16 model/labels/baseline, the TX -40 dB
safety ceiling, and every rf-adapt-prep1 asset stay byte-identical to the deployed
base.

Fail-closed audits run BEFORE anything is emitted: red-line headers, red-line
contracts, protected dirs, canonical components, dependency closure, complete-delta,
patch self-containment, literal patch-over-base overlay == full, determinism (two
builds byte-identical), and independent unpack + sha256sum -c.

Run with:
    python3 -I scripts/package_fix10class24_realrf_finetune_pilot1.py
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

# ---- the 4-tar deployed base chain (in overlay order) ----
BASE_FULL_TAR = os.path.abspath(os.path.join(
    ROOT, os.pardir, os.pardir,
    "fix10class24_dualsdr_rxrecovery1_work",
    "sdr_rml24_fix10class24_dualsdr_rxrecovery1",
    "dist", "sdr_rml24_fix10class24_bf16_dualsdr2_rxrecovery1_full.tar.gz"))
BASE_PATCH_SINGLESDR = os.path.abspath(os.path.join(
    ROOT, os.pardir, os.pardir,
    "fix10class24_singlesdr_ab1_work",
    "sdr_rml24_fix10class24_singlesdr_ab1",
    "dist", "sdr_rml24_fix10class24_bf16_singlesdr_ab1_patch.tar.gz"))
BASE_PATCH_SCALARWL = os.path.abspath(os.path.join(
    ROOT, os.pardir, os.pardir,
    "fix10class24_scalarwl_4way_work",
    "sdr_rml24_fix10class24_scalarwl_4way",
    "dist", "sdr_rml24_fix10class24_bf16_scalarwl_4way_patch.tar.gz"))
BASE_PATCH_RFADAPT = os.path.abspath(os.path.join(
    ROOT, os.pardir,
    "sdr_rml24_fix10class24_dualsdr_rf_adapt_prep1",
    "dist", "sdr_rml24_fix10class24_dualsdr_rf_adapt_prep1_patch.tar.gz"))

# Top-level directory name inside the rxrecovery1 full tarball (the deployed tree root
# on the board, unchanged across the whole chain).
BASE_TOP = "sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2"

PATCH_NAME = "sdr_rml24_fix10class24_realrf_finetune_pilot1_patch"
PATCH_SUMS_NAME = "FIX10CLASS24_REALRF_FINETUNE_PILOT1_PATCH_SHA256SUMS.txt"

# realrf-finetune-pilot1 drops nothing from the deployed base -- purely additive +
# in-place edits.
DELETE_LIST = []

# Directories never packaged (build products / python cache / replayer cache / output).
EXCLUDED_DIRS = {"host_tests/bin", "host_tests/__pycache__", "host_tools/__pycache__",
                 "scripts/__pycache__", "contracts/__pycache__", "dist", ".git",
                 "host_tools/.build_burst_cache", "host_tools/.replay24_cache",
                 "host_tools/.force_classify_cache", ".pytest_cache",
                 "results"}

# Transient files never packaged (stale host-test logs from a manual run).
EXCLUDED_FILES = {
    "host_tests/build_host_tests.log",
    "host_tests/run_tests.log",
}

# DERIVED SHA256SUMS artifacts left at the board root by earlier deliveries in the base
# chain.  They are regenerated by their own packagers, are stale in this working tree,
# and sit at the board root only once their patch is applied -- so they must never enter
# the change-set comparison (base has them, the working tree may not, and vice versa).
DERIVED_SUMS_NAMES = {
    "SHA256SUMS.txt",                                   # rxrecovery1 full (stale)
    "FIX10CLASS24_SINGLESDR_AB1_PATCH_SHA256SUMS.txt",  # singlesdr-ab1 patch
    "FIX10CLASS24_SCALARWL_4WAY_PATCH_SHA256SUMS.txt",  # scalarwl-4way patch
}

# Directories whose base contents must be byte-identical to the deployed base
# (model / weights / labels / preprocess / mapping / frozen 24-class assets).
PROTECTED_DIRS = ("model_rml23/", "model_12class/", "deployment_golden/",
                  "model_rml24_bf16/", "baselines/", "clean24_smoke/",
                  "contracts/")

# RED LINE: recovery core, coarse-CFO recovery, transfer state machine, canonical
# frame, 24-class clean-IQ runner, the wide-linear header (rxrecovery1-modified), the
# dual-SDR runner, the singlesdr-ab1 single-SDR transfer + runner, and the scalarwl-4way
# core + runner.  realrf-finetune-pilot1 modifies NONE of these -- its capture runner
# REUSES the recovery core + D2 restore byte-for-byte.  All must be byte-identical to
# the deployed base.
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
    "board_package/iq_rf_loopback_24class_bf16_scalarwl_core.hpp",
    "board_package/iq_rf_loopback_24class_bf16_scalarwl_diag.hpp",
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
            if rel not in EXCLUDED_FILES and rel not in DERIVED_SUMS_NAMES:
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
            sys.exit("DETERMINISM FAILED: %s (two builds differ)" % tar_path)
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

    full_rels = set(r for r in list_files(full_dir))
    over_rels = set(r for r in list_files(over))
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
    for t in (BASE_FULL_TAR, BASE_PATCH_SINGLESDR, BASE_PATCH_SCALARWL,
              BASE_PATCH_RFADAPT):
        if not os.path.exists(t):
            sys.exit("missing base tar: %s" % t)

    work = tempfile.mkdtemp(prefix="pkg_fix10class24_realrf_finetune_pilot1_")
    try:
        # ---- base = rxrecovery1 FULL + singlesdr PATCH + scalarwl PATCH +
        #      rf-adapt-prep1 PATCH (the deployed board state pilot1 assumes) ----
        base_x = os.path.join(work, "base")
        os.makedirs(base_x)
        with tarfile.open(BASE_FULL_TAR, "r:gz") as t:
            t.extractall(base_x, filter="data")
        base_ref = os.path.join(base_x, BASE_TOP)
        if not os.path.isdir(base_ref):
            sys.exit("base missing top dir: %s" % BASE_TOP)
        for label, pt in (("singlesdr-ab1", BASE_PATCH_SINGLESDR),
                          ("scalarwl-4way", BASE_PATCH_SCALARWL),
                          ("rf-adapt-prep1", BASE_PATCH_RFADAPT)):
            with tarfile.open(pt, "r:gz") as t:
                t.extractall(base_ref, filter="data")
            print("base overlay: %s PATCH applied" % label)
        print("base chain: OK (rxrecovery1 FULL + singlesdr + scalarwl + rf-adapt)")

        # ---- full staging (current tree, minus derived root sums) ----
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
        print("delete-list audit: OK (no files dropped from the deployed base)")
        PATCH_FILES = sorted(new + changed)
        if not PATCH_FILES:
            sys.exit("empty change set")
        print("change-set audit: OK (%d new + %d changed = %d patch files)"
              % (len(new), len(changed), len(PATCH_FILES)))
        for rel in sorted(new):
            print("  new    : %s" % rel)
        for rel in sorted(changed):
            print("  changed: %s" % rel)

        # ---- audits ----
        v = verify_byte_identical(full, base_ref, RED_LINE_HEADERS, "red-line")
        if v:
            _fail("red-line header audit", v)
        print("red-line header audit: OK (%d headers byte-identical to the deployed base)"
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
        print("patch self-containment audit: OK (patch overlays onto the deployed base alone)")

        v = verify_patch_overlay(base_ref, p, full, PATCH_FILES)
        if v:
            _fail("patch-over-base overlay audit", v)
        print("patch-over-base overlay audit: OK (literal byte-level == full)")

        # ---- sums + tarball (PATCH only; base + patch == full is proven above) ----
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
        print("  %-30s files=%d ok=%d %s" % ("realrf-finetune-pilot1 patch", total,
                                              good, "PASS" if ok else "FAIL"))
        if not ok:
            sys.exit(1)

        print("== summary ==")
        print("  base rxrecovery1 full    sha256=%s" % sha256_of(BASE_FULL_TAR))
        print("  base singlesdr patch     sha256=%s" % sha256_of(BASE_PATCH_SINGLESDR))
        print("  base scalarwl patch      sha256=%s" % sha256_of(BASE_PATCH_SCALARWL))
        print("  base rf-adapt patch      sha256=%s" % sha256_of(BASE_PATCH_RFADAPT))
        print("  %-30s %d content-files  sha256=%s" %
              ("realrf-finetune-pilot1 patch", p_n, sha256_of(patch_tar)))
        print("  %s" % patch_tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
