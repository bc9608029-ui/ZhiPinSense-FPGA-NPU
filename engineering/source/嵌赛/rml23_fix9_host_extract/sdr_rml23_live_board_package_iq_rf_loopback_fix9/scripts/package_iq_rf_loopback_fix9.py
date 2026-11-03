#!/usr/bin/env python3
"""Package the RML23 Stage H-F / Route F fix9 as an independent patch plus the
merged full board package.

fix9 is built on top of the shipped fix8 package
(sdr_rml23_live_board_package_iq_rf_loopback_fix8.tar.gz, sha 2577b1c9…).  It is the
Route F fix9 "core-version" increment: the D2 physical RF closed loop with a genuine
23-class accuracy measurement.  A minimal-but-credible closed loop that takes RadioML
raw IQ through the non-training Route D2 reconstruction, transmits AC-only ci16 over a
50-ohm coax loopback, receives it back, runs the D2 restore, and classifies the result
with the ORIGINAL 24-class model folded to the 23 deployed classes — reporting a full
23-class accuracy + confusion matrix, never a PASS/FAIL gate.

  Task A (manifest parsing) -- analyze_route_d2_4ask.py fail-closed manifest parser
    * The fix8 parser dropped the first row unconditionally as a "header", so a
      headerless manifest silently lost its first data row.  The fix9 parser detects
      a header by inspecting the first field ("index" literal vs. integer data row),
      validates index/source_index uniqueness + class_name <-> class_index
      consistency + (with bin_dir) .bin existence/8192 bytes/SHA256, and raises on
      any violation -- nothing is silently dropped (dropped==0 truthfully reported).

  Task B (D2 RF artifact builder) -- scripts/build_route_d2_rf_artifacts.py (NEW)
    * Writes per-sample quantized_d2_2p56m[_cal]_%06d.ci16 (interleaved int16 LE,
      AC-ONLY) + recovered_tensor_d2[_cal]_%06d.f32 ([2,1024] fp32 = 8192 bytes) +
      a 24-column route_d2_rf_manifest.tsv.  Global K is chosen on the CALIBRATION
      subset only (K=2048 preferred, largest clip-free re-selected; no labels, never
      the holdout).  Calibration and holdout are separated via split_role, so the
      board has a genuine independent RF-gain calibration subset and scores only the
      holdout.  --calib-count 8 --holdout-count 30 (formal 690), --smoke (46).

  Task C (D2 sidecar loader) -- iq_digital_loopback.hpp load_d2_sidecar
    * New Loader C for input-kind radioml-d2-2p56m.  Reads route_d2_rf_manifest.tsv,
      carries per-file build-time D2 constants (original_dc_i/q, rec_scale) + split
      role, and fail-closes on SHA/size/sample-rate/class-consistency/unsafe-path
      exactly like the Route D loader.  FrozenIq gains d2_rec_scale +
      recovered_tensor_file/recovered_tensor_sha256.

  Task D (--rf-tx-target-rms scaling) -- iq_rf_loopback_transfer.hpp
    * transfer_one_file_rf gains a trailing target_rms.  It measures the native TX
      RMS/peak, predicts the post-scale peak, and scales toward target_rms ONLY when
      the predicted peak does not clip.  tx_clip_post==true means scaling was refused
      (fail-closed: no silent saturation) and tx_scale stays 1.0.  Default 0.0 = no-op.

  Task E (D2 RX restore) -- iq_digital_loopback.hpp apply_d2_restore_to_stream +
  select_classification_window
    * The RX stream is decimated (iq/2048 -> unit-RMS AC), the ONE global RF gain is
      undone, then apply_d2_restore_to_stream re-applies rec_scale (== ac_rms*2048/K)
      and adds back the build-time DC LAST (DC was removed before TX, so it is NOT
      rotated by the RF gain).  select_classification_window picks the ONE reference
      aligned [2,1024] window by bounded delay alignment with a scale-invariant LS
      complex gain (so a 1/16 count-domain scale is never mistaken for divergence).

  Task F (runner + phase) -- iq_rf_loopback_23class.hpp (NEW)
    * --phase=iq-rf-loopback-23class (gate9_phase.hpp + board_gate9_full_chain_rml23.cpp
      dispatch).  Requires --input-kind=radioml-d2-2p56m + --rf-path=direct-cable +
      --tx-atten <= -40.  Two passes: calibration subset (global RF gain only), then
      holdout subset (restore + classify, ONE window per file).  Every scored sample
      must first pass RF_PRESERVES_IQ (corr>=0.9, SNR>=6 dB, normalized_residual<=0.05,
      no TX/RX clip); excluded samples are counted under rf_excluded and never scored.

  Task G/H (accuracy + confusion matrix) -- memory-bounded report
    * Only the fixed 23x23 confusion matrix + 23 per-class counters are retained (no
      per-file results).  Four outputs under out_dir: route_f_fix9_summary.json
      (accuracy token ROUTE_F_23CLASS_ACCURACY_MEASURED, or
      ROUTE_F_23CLASS_ACCURACY_INVALID_DUE_TO_RF_FIDELITY when the RF gate blocked the
      run), route_f_fix9_confusion_23.csv (true x predicted, deployed labels),
      route_f_fix9_per_class.json (23 objects), and the detailed per-sample TSV.
      24->23 mapping via kSourceToDeployed + merge_logits_23 (AM-SSB-SC folds into
      AM-SSB-WC via logaddexp), from rml23_merged.hpp.

  Task I/J -- small D0 control (documentation) + memory bounded (peak RSS read-back)

  §14 (host tests) -- host_tests/test_iq_rf_loopback_23class.cpp (NEW)
    * 17 tests covering the D2 sidecar parse/mapping/SHA/split-role/sample-rate/
      unsafe-path rejections, apply_d2_restore, target-rms no-op/scale-up/refuse-clip,
      select_classification_window, merge_logits_23 / merge_predict, and a D2 restore
      end-to-end (DC + RF gain + restore + window selection).  Wired into
      build_host_tests.sh + run_tests.sh.

It touches NOTHING outside Stage H-F / Route F + Route D2: no model / labels / golden /
production preprocessing / production read_rx default libiio path / RTL / XDC /
bitstream / Flash; no Stage G A/B/C/D semantics; no fix7/fix8 artifact is overwritten.

Produces, under dist/ (leaving every earlier package untouched, INCLUDING the fix8
package it builds on):

  1. sdr_rml23_live_iq_rf_loopback_fix9_patch.tar.gz          (Route F + D2 fix9 only)
  2. sdr_rml23_live_board_package_iq_rf_loopback_fix9.tar.gz  (fix8 full + fix9)

The fix9 patch is relative to the fix8 merged package (2577b1c9…).  The merged full
is that fix8 package + the fix9 files.  Modified files are carried with their FULL
working-tree content (fix8 baseline + fix9), so the patch is self-contained.

A dependency-closure audit (audit_dependency_closure) walks the transitive #include
closure of every fix9 C/C++ file and ABORTS if any resolved header differs from the
fix8 baseline but is not in ROUTE_F_FIX9_FILES.  This is the same fail-closed guard
that fixed the 2d8b8bab… packaging bug in fix1 and has been retained through fix2..
fix8, so a modified header can never again be silently reverted.

Each tarball is self-contained: a top directory holding the changed files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten.

stdlib only.  Run with:  python3 scripts/package_iq_rf_loopback_fix9.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_iq_rf_loopback_fix8.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_iq_rf_loopback_fix8"

PATCH_NAME = "sdr_rml23_live_iq_rf_loopback_fix9_patch"
PATCH_SUMS_NAME = "IQ_RF_LOOPBACK_FIX9_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_rf_loopback_fix9"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# fix9 files, relative to the repo root.  New files carried in full; modified files
# as fix8 baseline + fix9.
ROUTE_F_FIX9_FILES = [
    # Task C (D2 sidecar loader) -- MODIFIED
    "board_package/iq_digital_loopback.hpp",             # MODIFIED (load_d2_sidecar + restore + window)
    # Task D (target_rms scaling) -- MODIFIED
    "board_package/iq_rf_loopback_transfer.hpp",         # MODIFIED (target_rms + tx_clip_post fail-closed)
    # Task F (runner + phase) -- NEW
    "board_package/iq_rf_loopback_23class.hpp",          # NEW (D2 RF closed loop + 23-class runner)
    # wiring -- MODIFIED
    "board_package/board_gate9_full_chain_rml23.cpp",    # MODIFIED (23class phase wrapper + dispatch)
    "board_package/gate9_phase.hpp",                     # MODIFIED (iq-rf-loopback-23class phase name)
    # Task A (manifest parsing) -- MODIFIED
    "scripts/analyze_route_d2_4ask.py",                  # MODIFIED (fail-closed header-detect manifest parser)
    # Task B (D2 RF artifact builder) -- NEW
    "scripts/build_route_d2_rf_artifacts.py",            # NEW (ci16 + f32 + 24-col manifest builder)
    # §14 host tests -- NEW / MODIFIED
    "host_tests/test_iq_rf_loopback_23class.cpp",        # NEW (17 tests, D2 restore + 23-class)
    "host_tests/build_host_tests.sh",                    # MODIFIED (build 23class test)
    "host_tests/run_tests.sh",                           # MODIFIED (run 23class test)
    # packaging + record -- NEW
    "scripts/package_iq_rf_loopback_fix9.py",            # NEW (this packager)
    "docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX9_AUDIT.md",  # NEW (audit + record)
]

_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"')
_CPP_EXT = (".cpp", ".hpp", ".h", ".cc", ".cxx")


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_text(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
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


def _cpp_includes(path):
    """Yield the quote-included paths (as written) from a C/C++ file."""
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _INCLUDE_RE.match(line)
            if m:
                out.append(m.group(1))
    return out


def _rel_of(base, path):
    return os.path.relpath(os.path.abspath(path), base).replace(os.sep, "/")


def audit_dependency_closure(base_dir):
    """Prevent a 'modified header silently reverted to fix8 baseline' bug.

    Walk the transitive #include closure of every fix9 C/C++ file.  For each
    resolved header whose bytes DIFFER from the fix8 baseline (or which does not
    exist in the baseline at all), require it to be in ROUTE_F_FIX9_FILES --
    otherwise the merged full package would carry the stale baseline copy (or drop
    the header entirely) and the board compile would fail.  Returns a sorted list
    of violations (repo-root-relative paths); empty means the closure is safe.
    """
    base_sha = {}
    for dirpath, dirnames, filenames in os.walk(base_dir):
        dirnames.sort()
        for name in filenames:
            full = os.path.join(dirpath, name)
            base_sha[_rel_of(base_dir, full)] = sha256_of(full)

    fix9_set = set(ROUTE_F_FIX9_FILES)
    violations = set()
    seen = set()
    queue = [rel for rel in ROUTE_F_FIX9_FILES if rel.endswith(_CPP_EXT)]

    while queue:
        rel = queue.pop()
        abs_path = os.path.join(ROOT, rel.replace("/", os.sep))
        if abs_path in seen:
            continue
        seen.add(abs_path)
        if not os.path.exists(abs_path):
            continue
        for inc in _cpp_includes(abs_path):
            resolved = os.path.normpath(os.path.join(os.path.dirname(abs_path), inc))
            rrel = _rel_of(ROOT, resolved)
            if not os.path.exists(resolved):
                continue  # board-toolchain/system header not present in the tree
            if rrel in base_sha:
                if sha256_of(resolved) != base_sha[rrel] and rrel not in fix9_set:
                    violations.add(rrel)
            else:
                # header present in working tree but absent from baseline
                if rrel not in fix9_set:
                    violations.add(rrel)
            if resolved not in seen:
                queue.append(rrel)

    return sorted(violations)


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    for rel in ROUTE_F_FIX9_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    work = tempfile.mkdtemp(prefix="pkg_rfloop_fix9_")
    try:
        # ---- extract baseline once ----
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- dependency-closure audit (fail-closed, before any package is built) ----
        violations = audit_dependency_closure(base)
        if violations:
            print("dependency-closure audit FAILED: the following working-tree "
                  "headers differ from the fix8 baseline (or are absent from it) "
                  "but are NOT listed in ROUTE_F_FIX9_FILES:", file=sys.stderr)
            for v in violations:
                print("  " + v, file=sys.stderr)
            print("Add them to ROUTE_F_FIX9_FILES so the merged package carries their "
                  "working-tree content.", file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK (all changed headers covered by ROUTE_F_FIX9_FILES)")

        # ---- 1. fix9 patch (fix9 only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_F_FIX9_FILES:
            copy_from_root(p, rel)
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: fix8 baseline + fix9 ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in ROUTE_F_FIX9_FILES:
            copy_from_root(full, rel)
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix9 patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (fix8 + fix9)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-32s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix9 patch", p_tar, p_n),
            ("merged full (fix8 + fix9)", full_tar, full_n),
        ]:
            print("  %-32s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
