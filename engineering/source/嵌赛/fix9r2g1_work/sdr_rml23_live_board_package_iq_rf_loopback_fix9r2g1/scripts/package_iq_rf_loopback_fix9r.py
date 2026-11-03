#!/usr/bin/env python3
"""Package the RML23 Route F fix9r as an independent patch plus the merged full
board package.

fix9r is built on top of the shipped fix9 package
(sdr_rml23_live_board_package_iq_rf_loopback_fix9.tar.gz, sha 2205750c7d…).  It is the
Route F "per-file recovery" increment: fix9 measured 23-class accuracy at 10.87% because
its ONE global complex phase cannot undo the per-file TX-LO phase that re-keys on every
tx_start_cyclic.  fix9r brackets every payload with a known Zadoff-Chu TRAINING FRAME
(preamble + tail, category-independent, never the payload -- §7 leak ban), then recovers
gain/phase/timing/CFO/SRO/drift PER FILE from the preamble and applies the inverse before
the D2 restore chain.  The output is the same measurement-only 23-class accuracy +
confusion matrix, never a PASS/FAIL gate.

  Task A (root-cause analyzer) -- scripts/analyze_iq_rf_loopback_recovery.py (NEW)
    * Classifies the fix9 board log into PER_FILE_PHASE_UNRECOVERED /
      PER_FILE_GAIN_UNRECOVERED / CFO_PHASE_DRIFT / IQ_SWAP_OR_CONJUGATE /
      MODEL_DOMAIN_RECOVERY_NOT_PROVEN / NOT_PROVEN, with a built-in 9/9 synthetic
      self-test.

  Task B (exact 46-sample baseline) -- scripts/build_route_f_fix9r_exact_baseline.py (NEW)
    * Maps the 24-column route_d2_rf_manifest.tsv to the exact 46-holdout
      route_f_fix9r_exact_baseline.tsv (source_index / sha256 / deployed_class /
      modulation / split_role), fail-closed on malformed rows.  5/5 self-test.

  Task C/D (training frame + per-file recovery) -- iq_rf_training_frame.hpp (NEW) +
  iq_rf_per_frame_recovery.hpp (NEW)
    * Zadoff-Chu preamble (root 1) + tail (root 3), burst
      [preamble 1024][guard 2048][payload 53760][guard 2048][tail 1024] @ 2.56 MSPS.
      estimate() finds the preamble peak, LS complex gain, tail re-location SRO, and
      preamble-vs-tail CFO; apply() undoes timing/gain/phase/CFO/SRO.

  Task D/E/F/G (transfer + runner) -- iq_rf_loopback_transfer_fix9r.hpp (NEW) +
  iq_rf_fix9r_baseline.hpp (NEW) + iq_rf_loopback_23class_fix9r.hpp (NEW)
    * transfer_one_file_rf_fix9r builds the burst and emits it through the verified
      PlutoTx (loopback=0, --tx-atten <= -40 hard ceiling, TX DMA SHA re-check).
      run_iq_rf_loopback_23class_fix9r does ONE pass over the holdout: per-file
      recover -> int16 -> D2 restore (rec_scale, DC last) -> select window -> NPU
      infer -> merge_logits_23 -> argmax.  RF fidelity gate: training_corr >= 0.9 and
      training_residual <= 0.05, else rf_excluded (never scored).  Tokens:
      ROUTE_F_MEASUREMENT_COMPLETE / ROUTE_F_RF_FIDELITY_PASS /
      ROUTE_F_MODEL_DOMAIN_RECOVERY_NOT_PROVEN / ROUTE_F_23CLASS_ACCURACY_REGRESSION_PASS|_FAIL.

  Task H (host tests) -- host_tests/test_iq_rf_loopback_23class_fix9r.cpp (NEW)
    * 24 scenarios / 71 checks covering Zadoff-Chu properties, burst structure, the
      per-file estimator (identity/gain/phase/timing/CFO/SRO + SRO-direction ramp),
      transfer structural checks, and the fail-closed baseline loader.  Wired into
      build_host_tests.sh + run_tests.sh.

It touches NOTHING outside Route F + the fix9r wiring: no model / labels / 24->23 merge
rules / golden / production preprocessing / production read_rx libiio path / RTL / XDC /
bitstream / Flash; fix9's verified internal digital-loopback and same-machine RF paths are
reused by #include only, never modified; the RF safety ceiling (kSafeTxCeilingDb=-40.0 /
kSafeTxAttenDb=-89.75) is unchanged.

IMPORTANT (fix10 pause): Route G fix10 (double-SDR) is PAUSED and its on-disk files are
preserved.  A few wiring files (gate9_phase.hpp, board_gate9_full_chain_rml23.cpp,
build_host_tests.sh, run_tests.sh) therefore carry BOTH fix9r and fix10 edits on disk, and
sdr_adapter/pluto_device.hpp carries the fix10 host-test CFO/SRO injection.  This packager
reconstructs those four wiring files to their FIX9R-ONLY content by removing the fix10
edits, so the produced package is exactly fix9 + fix9r (no fix10).  The fix10 on-disk
files are never touched, and pluto_device.hpp is carried as the unchanged fix9 baseline.

Produces, under dist/ (leaving every earlier package untouched, INCLUDING the fix9 package
it builds on):

  1. sdr_rml23_live_iq_rf_loopback_fix9r_patch.tar.gz          (Route F fix9r only)
  2. sdr_rml23_live_board_package_iq_rf_loopback_fix9r.tar.gz  (fix9 full + fix9r)

Each tarball is self-contained: a top directory holding the changed files plus a SHA256SUMS
file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten.

A dependency-closure audit walks the transitive #include closure of every fix9r C/C++ file
AGAINST THE CLEAN full tree (fix9 baseline + fix9r-only files) and ABORTS if any resolved
header differs from the fix9 baseline but is not in ROUTE_F_FIX9R_FILES.

stdlib only.  Run with:  python3 scripts/package_iq_rf_loopback_fix9r.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_iq_rf_loopback_fix9.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_iq_rf_loopback_fix9"
BASE_SHA = "2205750c7d1a135bae805a2e772c8a23e1f81742159139a3a6a7fe3964f5f16d"

PATCH_NAME = "sdr_rml23_live_iq_rf_loopback_fix9r_patch"
PATCH_SUMS_NAME = "IQ_RF_LOOPBACK_FIX9R_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_rf_loopback_fix9r"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# fix9r files, relative to the repo root.  NEW files are copied verbatim from the
# working tree (they are fix9r-specific and carry no fix10 edits).  MODIFIED files
# are the four wiring files that share fix10 edits on disk; they are reconstructed
# to their fix9r-only content by the transforms in _FIX10_REMOVAL below.
ROUTE_F_FIX9R_NEW_FILES = [
    "board_package/iq_rf_training_frame.hpp",                 # NEW (Task C)
    "board_package/iq_rf_per_frame_recovery.hpp",             # NEW (Task C/D)
    "board_package/iq_rf_loopback_transfer_fix9r.hpp",        # NEW (Task D)
    "board_package/iq_rf_fix9r_baseline.hpp",                 # NEW (Task E)
    "board_package/iq_rf_loopback_23class_fix9r.hpp",         # NEW (Task E/F/G)
    "scripts/analyze_iq_rf_loopback_recovery.py",             # NEW (Task A)
    "scripts/build_route_f_fix9r_exact_baseline.py",          # NEW (Task B)
    "host_tests/test_iq_rf_loopback_23class_fix9r.cpp",       # NEW (Task H)
    "scripts/package_iq_rf_loopback_fix9r.py",                # NEW (this packager)
    "docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX9R_AUDIT.md", # NEW (audit + record)
]

ROUTE_F_FIX9R_MODIFIED_FILES = [
    "board_package/gate9_phase.hpp",                          # MODIFIED (add fix9r phase)
    "board_package/board_gate9_full_chain_rml23.cpp",         # MODIFIED (fix9r runner + dispatch)
    "host_tests/build_host_tests.sh",                         # MODIFIED (build fix9r test)
    "host_tests/run_tests.sh",                                # MODIFIED (run fix9r test)
]

ROUTE_F_FIX9R_FILES = ROUTE_F_FIX9R_NEW_FILES + ROUTE_F_FIX9R_MODIFIED_FILES

_SEP = "// " + "-" * 75


def _remove_fix10_board(text):
    """Return board_gate9_full_chain_rml23.cpp with the fix10 edits removed."""
    # 1. the fix10 include
    old = '#include "iq_rf_loopback_23class_fix9r.hpp"\n#include "iq_external_rf_rx.hpp"\n'
    assert text.count(old) == 1, "board include anchor not unique/found"
    text = text.replace(old, '#include "iq_rf_loopback_23class_fix9r.hpp"\n')

    # 2. the two fix10 runner functions (from the fix10 rx comment's separator through
    #    the level-sweep function's closing brace), leaving the next phase's separator.
    left_anchor = "// Phase iq-external-rf-rx-23class: Stage H-G / Route G fix10 Task D/F/G"
    right_anchor = "// Phase iq-digital-loopback-sweep: Stage H-E / Route E fix3 -- locate and fix the"
    assert text.count(left_anchor) == 1, "fix10 rx comment not unique/found"
    assert text.count(right_anchor) == 1, "digital-loopback-sweep comment not unique/found"
    left = text.index(left_anchor)
    right = text.index(right_anchor)
    sep_before_left = text.rindex(_SEP, 0, left)
    sep_before_right = text.rindex(_SEP, 0, right)
    text = text[:sep_before_left] + text[sep_before_right:]

    # 3. the fix10 phases in the unknown-phase error string
    old = ('"iq-rf-loopback-23class|iq-rf-loopback-23class-fix9r|"\n'
           '                    "iq-external-rf-rx-23class|"\n'
           '                    "iq-external-rf-level-sweep)");')
    assert text.count(old) == 1, "error-string fix10 phases not unique/found"
    text = text.replace(old, '"iq-rf-loopback-23class|iq-rf-loopback-23class-fix9r)");')

    # 4. the fix10 dispatch branches
    old = ('        else if (phase == "iq-rf-loopback-23class-fix9r")\n'
           '            rc = run_iq_rf_loopback_23class_fix9r(npu, contract, out, sock, timing, argc, argv);\n'
           '        else if (phase == "iq-external-rf-rx-23class")\n'
           '            rc = run_iq_external_rf_rx_23class(npu, contract, out, sock, timing, argc, argv);\n'
           '        else if (phase == "iq-external-rf-level-sweep")\n'
           '            rc = run_iq_external_rf_level_sweep(npu, contract, out, sock, timing, argc, argv);\n')
    assert text.count(old) == 1, "fix10 dispatch not unique/found"
    text = text.replace(old,
        '        else if (phase == "iq-rf-loopback-23class-fix9r")\n'
        '            rc = run_iq_rf_loopback_23class_fix9r(npu, contract, out, sock, timing, argc, argv);\n')

    assert "iq-external-rf" not in text and "extrf::" not in text and "fix10" not in text
    return text


def _remove_fix10_gate9_phase(text):
    old = ('p == "iq-rf-loopback-23class-fix9r" ||\n'
           '           p == "iq-external-rf-rx-23class" ||\n'
           '           p == "iq-external-rf-level-sweep";')
    assert text.count(old) == 1, "gate9_phase fix10 phases not unique/found"
    return text.replace(old, 'p == "iq-rf-loopback-23class-fix9r";')


def _remove_fix10_build(text):
    old = ('test_iq_rf_loopback_23class_fix9r.cpp ../sdr_adapter/pluto_tx.cpp '
           '-o bin/test_iq_rf_loopback_23class_fix9r\n'
           '\n'
           'echo "== build test_iq_external_rf_rx_23class =="\n'
           '$CXX $FLAGS test_iq_external_rf_rx_23class.cpp -o bin/test_iq_external_rf_rx_23class\n'
           '\n'
           'echo "== build test_pluto_external_tx =="\n'
           '$CXX $FLAGS test_pluto_external_tx.cpp -o bin/test_pluto_external_tx\n'
           '\n'
           'echo "build_host_tests.sh: OK')
    assert text.count(old) == 1, "build fix10 block not unique/found"
    text = text.replace(old, 'test_iq_rf_loopback_23class_fix9r.cpp ../sdr_adapter/pluto_tx.cpp '
                             '-o bin/test_iq_rf_loopback_23class_fix9r\n\n'
                             'echo "build_host_tests.sh: OK')
    old = 'test_iq_rf_loopback_23class_fix9r,test_iq_external_rf_rx_23class,test_pluto_external_tx}'
    assert text.count(old) == 1, "build echo fix10 entries not unique/found"
    text = text.replace(old, 'test_iq_rf_loopback_23class_fix9r}')
    assert "iq_external_rf_rx" not in text and "pluto_external_tx" not in text
    return text


def _remove_fix10_run(text):
    old = ('./bin/test_iq_rf_loopback_23class_fix9r || rc=1\n'
           './bin/test_iq_external_rf_rx_23class || rc=1\n'
           './bin/test_pluto_external_tx || rc=1\n')
    assert text.count(old) == 1, "run fix10 lines not unique/found"
    text = text.replace(old, './bin/test_iq_rf_loopback_23class_fix9r || rc=1\n')
    assert "iq_external_rf_rx" not in text and "pluto_external_tx" not in text
    return text


_FIX10_REMOVAL = {
    "board_package/board_gate9_full_chain_rml23.cpp": _remove_fix10_board,
    "board_package/gate9_phase.hpp": _remove_fix10_gate9_phase,
    "host_tests/build_host_tests.sh": _remove_fix10_build,
    "host_tests/run_tests.sh": _remove_fix10_run,
}


def _fix9r_content(rel):
    """Return the fix9r-only content of a file (reconstructed for MODIFIED files)."""
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8", newline="\n") as f:
        text = f.read()
    if rel in _FIX10_REMOVAL:
        return _FIX10_REMOVAL[rel](text)
    return text


_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"')
_CPP_EXT = (".cpp", ".hpp", ".h", ".cc", ".cxx")


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def write_text(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.chmod(path, mode)


def write_bytes(path, data, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    os.chmod(path, mode)


def copy_from_root(stage, rel):
    src = os.path.join(ROOT, rel)
    dst = os.path.join(stage, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def list_files(stage):
    out = []
    for dirpath, dirnames, filenames in os.walk(stage):
        dirnames.sort()
        for name in filenames:
            full = os.path.join(dirpath, name)
            out.append(os.path.relpath(full, stage).replace(os.sep, "/"))
    return sorted(out)


def write_sums(stage, sums_name):
    rels = [r for r in list_files(stage) if r != sums_name]
    lines = []
    for rel in rels:
        lines.append("%s *%s\n" % (sha256_of(os.path.join(stage, rel.replace("/", os.sep))), rel))
    write_text(os.path.join(stage, sums_name), "".join(sorted(lines)))
    return len(rels)


def make_tar(stage, tar_path):
    """Deterministic tar.gz: fixed member metadata + gzip mtime=0, no FNAME."""
    top = os.path.basename(stage.rstrip("/\\"))
    raw = tar_path + ".tmp.tar"
    with tarfile.open(raw, "w", format=tarfile.GNU_FORMAT) as t:
        for rel in list_files(stage):
            full = os.path.join(stage, rel.replace("/", os.sep))
            arc = os.path.join(top, rel).replace(os.sep, "/")
            info = t.gettarinfo(full, arcname=arc)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            with open(full, "rb") as f:
                t.addfile(info, f)
    with open(raw, "rb") as fin:
        with gzip.GzipFile(filename="", mode="wb", fileobj=open(tar_path, "wb"),
                           compresslevel=9, mtime=0) as gz:
            shutil.copyfileobj(fin, gz)
    os.remove(raw)


def verify_tar(tar_path, sums_name, topdir):
    """Re-extract the tarball and check every hash, returning (ok, count, good)."""
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(tar_path, "r:gz") as t:
            t.extractall(td)
        d = os.path.join(td, topdir)
        sums_path = os.path.join(d, sums_name)
        ok = 0
        bad = 0
        with open(sums_path, "r", encoding="utf-8") as f:
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


def _cpp_includes(text):
    out = []
    for line in text.splitlines():
        m = _INCLUDE_RE.match(line)
        if m:
            out.append(m.group(1))
    return out


def _rel_of(base, path):
    return os.path.relpath(os.path.abspath(path), base).replace(os.sep, "/")


def audit_dependency_closure(full_dir, base_dir):
    """Fail-closed closure audit over the CLEAN full tree.

    Walk the transitive #include closure of every fix9r C/C++ file (read from
    full_dir, which is fix9 baseline + fix9r-only content).  For each resolved
    header whose bytes DIFFER from the fix9 baseline (or are absent from it),
    require it to be in ROUTE_F_FIX9R_FILES.  Returns a sorted list of violations.
    """
    base_sha = {}
    for dirpath, dirnames, filenames in os.walk(base_dir):
        dirnames.sort()
        for name in filenames:
            full = os.path.join(dirpath, name)
            base_sha[_rel_of(base_dir, full)] = sha256_of(full)

    fix9r_set = set(ROUTE_F_FIX9R_FILES)
    violations = set()
    seen = set()
    queue = [rel for rel in ROUTE_F_FIX9R_FILES if rel.endswith(_CPP_EXT)]

    while queue:
        rel = queue.pop()
        abs_path = os.path.join(full_dir, rel.replace("/", os.sep))
        if abs_path in seen:
            continue
        seen.add(abs_path)
        if not os.path.exists(abs_path):
            continue
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            includes = _cpp_includes(f.read())
        for inc in includes:
            resolved = os.path.normpath(os.path.join(os.path.dirname(abs_path), inc))
            rrel = _rel_of(full_dir, resolved)
            if not os.path.exists(resolved):
                continue  # board-toolchain/system header not present in the tree
            if rrel in base_sha:
                if sha256_of(resolved) != base_sha[rrel] and rrel not in fix9r_set:
                    violations.add(rrel)
            else:
                if rrel not in fix9r_set:
                    violations.add(rrel)
            if resolved not in seen:
                queue.append(rrel)

    return sorted(violations)


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    actual = sha256_of(BASE_TAR)
    if actual != BASE_SHA:
        sys.exit("baseline package SHA mismatch:\n  expected %s\n  got      %s" % (BASE_SHA, actual))

    # Every listed file must exist on disk (reconstructed files are checked later).
    for rel in ROUTE_F_FIX9R_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    # Pre-compute the fix9r-only content of every file (reconstructing the MODIFIED
    # wiring files to strip the paused fix10 edits) and fail-closed on any drift.
    content = {}
    for rel in ROUTE_F_FIX9R_FILES:
        content[rel] = _fix9r_content(rel)

    work = tempfile.mkdtemp(prefix="pkg_rfloop_fix9r_")
    try:
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- clean full tree: fix9 baseline + fix9r-only files ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in ROUTE_F_FIX9R_FILES:
            write_bytes(os.path.join(full, rel.replace("/", os.sep)),
                        content[rel].encode("utf-8"))

        # ---- dependency-closure audit (fail-closed) ----
        violations = audit_dependency_closure(full, base)
        if violations:
            print("dependency-closure audit FAILED: headers differ from the fix9 "
                  "baseline (or are absent from it) but are NOT listed in "
                  "ROUTE_F_FIX9R_FILES:", file=sys.stderr)
            for v in violations:
                print("  " + v, file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK (all changed headers covered by ROUTE_F_FIX9R_FILES)")

        # ---- 1. fix9r patch (fix9r only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_F_FIX9R_FILES:
            write_bytes(os.path.join(p, rel.replace("/", os.sep)),
                        content[rel].encode("utf-8"))
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: fix9 baseline + fix9r ----
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix9r patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (fix9 + fix9r)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-32s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix9r patch", p_tar, p_n),
            ("merged full (fix9 + fix9r)", full_tar, full_n),
        ]:
            print("  %-32s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
