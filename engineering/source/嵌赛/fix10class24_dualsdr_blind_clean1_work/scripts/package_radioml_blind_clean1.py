#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Package the fix10class24-dualsdr-blind-clean1 board-test delivery (offline).

The deployed board state is the npu-ab1 FULL tree (tx-rms-sweep1 + npu-ab1 PATCH +
scalarwl-4way PATCH), with gate9_phase/board_gate9 having been advanced to the dc-ab1
state (3 phases: npu + dualsdr + singlesdr).  This delivery is PURELY ADDITIVE on top
(deletions empty) and delivers the BLIND (no-sample-prior) pure-modulation dual-SDR
runner.  It produces TWO deterministic FLAT tarballs (PATCH + INPUTS):

  PATCH package  -- the exact change set (11 new + 2 changed + 1 vendored-verbatim):
    board_package/iq_blind_rx_24class_bf16_fix10.hpp   (RX-only blind runner, new phase)
    board_package/gate9_phase.hpp                      (+1 phase predicate line)
    board_package/board_gate9_full_chain_rml23.cpp     (include + wrapper + error-text + dispatch)
    contract/blind_rx_sampling_contract.{json,md}      (frozen authority)
    scripts/radioml_blind_clean_contract.py            (TX payload producer, frozen constants)
    scripts/radioml_clean_contract.py                  (vendored verbatim from fix10clean2a)
    host_tools/pc_tx_blind_clean.py                    (PC TX service, server :39010)
    scripts/judge_radioml_blind_clean.py               (offline judger, 3-layer + routing)
    scripts/digital_replay_radioml_blind_clean.py      (3-layer digital replay)
    scripts/run_radioml_blind_clean.sh                 (board orchestration)
    scripts/package_radioml_blind_clean1.py            (this packager)
    host_tests/test_radioml_blind_clean.py             (host test, 14/14)
    docs/M29_RML24_FIX10CLASS24_DUALSDR_BLIND_CLEAN1_BOARDTEST.md

Red lines stay byte-identical to the deployed base: the production recovery/runner
headers, the 24-class BF16 model json/raw, the 0.100 fidelity gate, the frozen assets.
No model / preprocessor / recovery / threshold is touched (this test does not USE the
recovery chain, but it also does not modify it).

INPUTS package -- the TX-payload DATA package (24 x <source_index>.i16 +
blind_tx_manifest.tsv + blind_tx_summary.json + SHA256SUMS.txt), GENERATED HERE by
running scripts/radioml_blind_clean_contract.py into a fresh dir (the frozen TX-scale
constants are re-verified by the generator's own self-test before packaging).

Run with:
    python3 -I scripts/package_radioml_blind_clean1.py
"""

import difflib
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

# The deployed board state this delivery overlays (npu-ab1 FULL, for include-closure).
BASE_DIR = os.path.abspath(os.path.join(
    ROOT, os.pardir,
    "fix10class24_original_radioml_npu_ab1_work",
    "sdr_rml24_fix10class24_original_radioml_npu_ab1"))

# The dc-ab1 work root (diff base for the two MODIFIED files: gate9_phase + board_gate9).
DCAB_DIR = os.path.abspath(os.path.join(
    ROOT, os.pardir, "fix10class24_original_radioml_dc_ab1_work"))

# The fix10clean2a work root (vendor source for scripts/radioml_clean_contract.py).
CLEAN2A_DIR = os.path.abspath(os.path.join(
    ROOT, os.pardir, "fix10clean2a_work"))

PATCH_NAME = "sdr_rml24_fix10class24_dualsdr_blind_clean1_patch"
PATCH_SUMS_NAME = "FIX10CLASS24_DUALSDR_BLIND_CLEAN1_PATCH_SHA256SUMS.txt"

INPUTS_NAME = "sdr_rml24_fix10class24_dualsdr_blind_clean1_inputs"
INPUTS_SUMS_NAME = "FIX10CLASS24_DUALSDR_BLIND_CLEAN1_INPUTS_SHA256SUMS.txt"

# The exact change set this delivery must produce, nothing else.
EXPECTED_PATCH_FILES = (
    "board_package/iq_blind_rx_24class_bf16_fix10.hpp",
    "board_package/gate9_phase.hpp",
    "board_package/board_gate9_full_chain_rml23.cpp",
    "contract/blind_rx_sampling_contract.json",
    "contract/blind_rx_sampling_contract.md",
    "docs/M29_RML24_FIX10CLASS24_DUALSDR_BLIND_CLEAN1_BOARDTEST.md",
    "host_tests/test_radioml_blind_clean.py",
    "host_tools/pc_tx_blind_clean.py",
    "scripts/digital_replay_radioml_blind_clean.py",
    "scripts/judge_radioml_blind_clean.py",
    "scripts/package_radioml_blind_clean1.py",
    "scripts/radioml_blind_clean_contract.py",
    "scripts/radioml_clean_contract.py",
    "scripts/run_radioml_blind_clean.sh",
)

# Files vendored VERBATIM from another tree (same relative path in the source tree).
VENDORED_VERBATIM = (
    # scripts/radioml_clean_contract.py <- fix10clean2a_work/scripts/
    ("scripts/radioml_clean_contract.py", CLEAN2A_DIR),
)

# The two MODIFIED files: they must differ from the dc-ab1 base by EXACTLY the hunks.
CHANGED_FILES = (
    "board_package/gate9_phase.hpp",
    "board_package/board_gate9_full_chain_rml23.cpp",
)

# Production headers my runner must resolve against the deployed base (i.e. I must NOT
# have touched or omitted them).  A missing entry = include-closure failure.
RUNNER_BASE_HEADERS = (
    "board_package/chain_common.hpp",
    "board_package/npu_classifier24.hpp",
    "board_package/board_common.hpp",
    "board_package/iq_digital_loopback_sync.hpp",
    "board_package/rml24_raw.hpp",
    "board_package/rf_fix_helpers.hpp",
    "sdr_adapter/latency_stats.hpp",
    "sdr_adapter/resource_snapshot.hpp",
    "sdr_adapter/pluto_device.hpp",
    "sdr_adapter/device_state_guard.hpp",
    "sdr_adapter/tcp_control_client.hpp",
    "sdr_adapter/sha256.hpp",
)

EXCLUDED_DIRS = ("__pycache__", "dist", ".git", "results")
EXCLUDED_SUFFIX = (".pyc",)


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
    for rel, src_dir in VENDORED_VERBATIM:
        mine = os.path.join(ROOT, rel.replace("/", os.sep))
        theirs = os.path.join(src_dir, rel.replace("/", os.sep))
        if not os.path.exists(theirs):
            bad.append(rel + " (missing in %s)" % src_dir)
        elif sha256_of(mine) != sha256_of(theirs):
            bad.append(rel + " (differs from %s)" % src_dir)
    if bad:
        _fail("vendored-verbatim audit", bad)
    print("vendored-verbatim audit: OK (%d files byte-identical to their source tree)"
          % len(VENDORED_VERBATIM))


def audit_changed_files():
    # gate9_phase.hpp: exactly the 1-line -> 2-line predicate change (add the blind
    # phase after the singlesdr phase), nothing else.
    base = open(os.path.join(DCAB_DIR, "board_package/gate9_phase.hpp"),
                encoding="utf-8").read().splitlines()
    mine = open(os.path.join(ROOT, "board_package/gate9_phase.hpp"),
                encoding="utf-8").read().splitlines()
    diff = list(difflib.unified_diff(base, mine, "base", "mine", lineterm=""))
    removed = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---")]
    added = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
    exp_removed = ['           p == "radioml-original-singlesdr-ab-24class-bf16-fix10";']
    exp_added = ['           p == "radioml-original-singlesdr-ab-24class-bf16-fix10" ||',
                 '           p == "iq-blind-rx-24class-bf16-fix10";']
    if removed != exp_removed or added != exp_added:
        _fail("gate9_phase.hpp red-line audit", [
            "diff vs dc-ab1 base:\n" + "\n".join(difflib.unified_diff(
                base, mine, "base", "mine", lineterm=""))])
    print("gate9_phase.hpp red-line audit: OK (single predicate line added, nothing else)")

    # board_gate9_full_chain_rml23.cpp: exactly 4 hunks (include + wrapper + error-text
    # + dispatch); only ONE line removed (the old error text); the blind phase is wired.
    base = open(os.path.join(DCAB_DIR, "board_package/board_gate9_full_chain_rml23.cpp"),
                encoding="utf-8").read().splitlines()
    mine = open(os.path.join(ROOT, "board_package/board_gate9_full_chain_rml23.cpp"),
                encoding="utf-8").read().splitlines()
    diff = list(difflib.unified_diff(base, mine, "base", "mine", lineterm=""))
    removed = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---")]
    added = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
    hunk_count = sum(1 for l in diff if l.startswith("@@"))
    added_text = "\n".join(added)
    bad = []
    if hunk_count != 4:
        bad.append("expected 4 hunks, got %d" % hunk_count)
    if removed != ['                    "radioml-original-singlesdr-ab-24class-bf16-fix10)");']:
        bad.append("unexpected removed lines: %r" % (removed,))
    for marker in ('#include "iq_blind_rx_24class_bf16_fix10.hpp"',
                   "int run_iq_blind_rx_24class_bf16_fix10(",
                   'phase == "iq-blind-rx-24class-bf16-fix10"',
                   '"iq-blind-rx-24class-bf16-fix10)"',
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
               "iq_pc_tx_board_rx", "iq_clean_iq_24class", "tcp_control_client",
               "sha256.hpp", "pluto_device", "device_state_guard")
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
    print("no-red-line-header audit: OK (change set adds only 1 new board header)")


def generate_tx_payload(dest):
    """Run scripts/radioml_blind_clean_contract.py into a fresh dir (refuses overwrite)."""
    gen = os.path.join(ROOT, "scripts", "radioml_blind_clean_contract.py")
    if os.path.exists(dest):
        sys.exit("payload dir already exists (refuse overwrite): %s" % dest)
    print("generating TX payload: %s --out-dir %s" % (gen, dest))
    cp = subprocess.run([sys.executable, "-I", gen, "--out-dir", dest],
                        cwd=ROOT, capture_output=True, text=True)
    if cp.returncode != 0:
        sys.exit("TX payload generation FAILED rc=%d\nstdout:\n%s\nstderr:\n%s"
                 % (cp.returncode, cp.stdout, cp.stderr))
    print(cp.stdout.strip())
    # Re-run the generator's self-test as an independent frozen-constant check.
    st = subprocess.run([sys.executable, "-I", gen, "--self-test"],
                        cwd=ROOT, capture_output=True, text=True)
    if st.returncode != 0:
        sys.exit("TX payload self-test FAILED rc=%d\n%s" % (st.returncode, st.stdout))
    print(st.stdout.strip())


def build_inputs_package():
    work = tempfile.mkdtemp(prefix="pkg_blind_clean1_input_")
    try:
        payload = os.path.join(work, "payload")
        generate_tx_payload(payload)

        # Verify the generated payload's own authority before re-packaging.
        i16 = sorted(f for f in os.listdir(payload) if f.endswith(".i16"))
        if len(i16) != 24:
            sys.exit("expected 24 .i16 files in %s, found %d" % (payload, len(i16)))
        manifest = os.path.join(payload, "blind_tx_manifest.tsv")
        if not os.path.isfile(manifest):
            sys.exit("missing blind_tx_manifest.tsv in %s" % payload)
        with open(manifest, encoding="utf-8") as f:
            nlines = len(f.read().rstrip("\n").split("\n"))
        if nlines != 25:
            sys.exit("expected blind_tx_manifest.tsv 25 lines (1 header + 24), got %d"
                     % nlines)

        gen_sums = os.path.join(payload, "SHA256SUMS.txt")
        if not os.path.isfile(gen_sums):
            sys.exit("missing generator SHA256SUMS.txt in %s" % payload)
        gen = {}
        for line in open(gen_sums, encoding="utf-8"):
            parts = line.split()
            if len(parts) >= 2:
                gen[parts[1]] = parts[0]
        for n in i16:
            if n not in gen or gen[n] != sha256_of(os.path.join(payload, n)):
                sys.exit("payload %s does not match generator SHA256SUMS.txt" % n)

        stage = os.path.join(work, INPUTS_NAME)
        os.makedirs(stage, exist_ok=True)
        for n in i16:
            shutil.copy2(os.path.join(payload, n), os.path.join(stage, n))
        shutil.copy2(manifest, os.path.join(stage, "blind_tx_manifest.tsv"))
        shutil.copy2(os.path.join(payload, "blind_tx_summary.json"),
                     os.path.join(stage, "blind_tx_summary.json"))
        n = write_sums(stage, INPUTS_SUMS_NAME)
        tar_path = os.path.join(DIST, INPUTS_NAME + ".tar.gz")
        build_tar_deterministic(stage, tar_path)
        print("determinism: OK (inputs tarball built twice, byte-identical)")
        shutil.copy2(os.path.join(stage, INPUTS_SUMS_NAME),
                     os.path.join(DIST, INPUTS_NAME + "_SHA256SUMS.txt"))
        print("== self-check ==")
        ok, total, good = verify_tar_flat(tar_path, INPUTS_SUMS_NAME)
        print("  %-48s files=%d ok=%d %s" % ("dualsdr-blind-clean1 inputs",
                                              total, good, "PASS" if ok else "FAIL"))
        if not ok:
            sys.exit(1)
        print("  %-40s %d content-files  sha256=%s" %
              ("dualsdr-blind-clean1 inputs", n, sha256_of(tar_path)))
        print("  %s" % tar_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    if not os.path.isdir(BASE_DIR):
        sys.exit("missing base tree: %s" % BASE_DIR)
    if not os.path.isdir(DCAB_DIR):
        sys.exit("missing dc-ab1 fork: %s" % DCAB_DIR)
    if not os.path.isdir(CLEAN2A_DIR):
        sys.exit("missing clean2a fork: %s" % CLEAN2A_DIR)

    audit_change_set()
    audit_vendored_verbatim()
    audit_changed_files()
    audit_include_closure()
    audit_no_red_line_headers()

    os.makedirs(DIST, exist_ok=True)
    work = tempfile.mkdtemp(prefix="pkg_blind_clean1_")
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
        print("  %-48s files=%d ok=%d %s" % ("dualsdr-blind-clean1 patch",
                                              total, good, "PASS" if ok else "FAIL"))
        if not ok:
            sys.exit(1)

        print("== summary ==")
        print("  base npu-ab1 tree         %s" % BASE_DIR)
        print("  %-40s %d content-files  sha256=%s" %
              ("dualsdr-blind-clean1 patch", n, sha256_of(tar_path)))
        print("  %s" % tar_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    build_inputs_package()


if __name__ == "__main__":
    main()
