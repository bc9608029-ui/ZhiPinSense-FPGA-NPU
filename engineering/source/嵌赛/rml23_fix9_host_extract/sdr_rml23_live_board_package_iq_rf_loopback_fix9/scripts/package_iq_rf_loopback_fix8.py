#!/usr/bin/env python3
"""Package the RML23 Stage H-F / Route F fix8 as an independent patch plus the
merged full board package.

fix8 is built on top of the shipped fix7 package
(sdr_rml23_live_board_package_iq_rf_loopback_fix7.tar.gz, sha 20d843c2…).  It is the
Route F fix8 increment: a 14-section spec that splits the TX/RX clipping evidence,
fixes the first-TX-off negative-control transient, adds a physical RF SAFE-OPERATING-
POINT level sweep, a Route D frozen-artifact audit, a non-training Route D2 4ASK
verdict, and the D-vs-D2 A/B gate.  Six mutually isolated subtasks:

  Task A (四) -- split TX/RX clipping
    * SyncFidelityMetrics.clipped (single bool) becomes tx_clipped / rx_clipped /
      tx_clip_count / rx_clip_count / tx_peak / rx_peak, with the clip rails DERIVED
      from DataFormatInfo.bits (TX16 -> +32767/-32768, RX12 -> +2047/-2048, never
      hardcoded).  The RF fidelity tokens split into RF_TX_CLIPPED / RF_RX_CLIPPED;
      RF_PRESERVES_IQ now requires tx_clipped == 0 AND rx_clipped == 0 AND corr >= 0.9
      AND residual <= 0.05 AND SNR >= 6 dB AND sync origin explainable AND DMA correct
      AND loopback == 0 AND negative control valid AND restore success.

  Task B (五) -- first-TX-off negative-control transient
    * The old single noise refill could read the tail of the just-stopped TX as
      "noise".  New sequence: tx_stop -> destroy/stop cyclic TX -> CONFIRM TX stopped
      (tx_running() == false) -> recreate_rx_buffer -> >=1 discard refill (NOT counted)
      -> capture 3 INDEPENDENT noise windows -> RMS median (floor for the SNR judgment).
      If the 3 windows are abnormally different, the runner fail-closes with
      RF_NEGATIVE_CONTROL_UNSTABLE.  Per-file records carry
      IQ_RF_LOOPBACK_NEGATIVE_CONTROL_DISCARD / _SAMPLE / _SUMMARY.

  Task C (六) -- --phase=iq-rf-loopback-level-sweep
    * RF SAFE OPERATING POINT scan (NO labels, NO NPU, NO classification): loopback=0,
      --rf-path=direct-cable, tx-atten=-40 (never raised), no auto TX power, no
      antenna, 50-ohm SMA.  Scan TX frozen-IQ RMS 512/1024/2048/4096/8192 x RX gain
      0/10/20/30 x (tone + PRBS + >=1 modulated); negative control before TX-on; a
      point is rejected on clip.  Outputs IQ_RF_LOOPBACK_LEVEL_SWEEP / _SELECTION
      (recommended_raw_complex_rms_counts / recommended_rx_gain / selection_reason).

  Task D (七) -- scripts/audit_route_d_artifacts.py
    * Route D frozen-artifact audit: 13-column manifest, 6-file existence per frame,
      no dangling symlinks, exact size/SHA, recovered tensor == 8192 bytes, quantized
      size == complex count.  Outputs ROUTE_D_ARTIFACT_AUDIT result=PASS|FAIL with
      missing/dangling/size_mismatch/sha_mismatch/manifest counts.

  Task E (八) -- non-training Route D2 4ASK verdict
    * analyze_route_d2_4ask.py now emits a compute_verdict token
      ROUTE_D2_4ASK_NON_RETRAINING_FIX_PROVEN only when the holdout 4ASK clearly
      recovers AND the other 3 classes do not regress; otherwise
      NON_RETRAINING_4ASK_FIX_NOT_PROVEN.  Global K only from unlabelled reconstruction
      error / quantisation utilisation / clip rate on a fixed calibration subset, held
      on an independent holdout, never label-search.  Writes D2 recovered tensors +
      a SHA-consistent d2_recovered_manifest.tsv.

  Task F (九) -- iq_rf_loopback_ab.hpp (the D-vs-D2 A/B gate)
    * A PURE, fail-closed 6-gate check: Route D audit PASS, Route D2 audit PASS, RF
      safe point selected, RF_PRESERVES_IQ, no clipping, negative control stable.  Any
      unsatisfied gate => allowed == false and the runner REFUSES to emit on the RF
      port.  --phase=iq-rf-loopback-ab never opens the device and never runs the NPU.

It touches NOTHING outside Stage H-F / Route F + Route D2: no model / labels / golden /
production preprocessing / production read_rx default libiio path / RTL / XDC /
bitstream / Flash; no Stage G A/B/C/D semantics; no digital/rf/ambient/live-rx
semantics; no fix7 artifact is overwritten.

Produces, under dist/ (leaving every earlier package untouched, INCLUDING the fix7
package it builds on):

  1. sdr_rml23_live_iq_rf_loopback_fix8_patch.tar.gz          (Route F + D2 fix8 only)
  2. sdr_rml23_live_board_package_iq_rf_loopback_fix8.tar.gz  (fix7 full + fix8)

The fix8 patch is relative to the fix7 merged package (20d843c2…).  The merged full
is that fix7 package + the fix8 files.  Modified files are carried with their FULL
working-tree content (fix7 baseline + fix8), so the patch is self-contained.

A dependency-closure audit (audit_dependency_closure) walks the transitive #include
closure of every fix8 C/C++ file and ABORTS if any resolved header differs from the
fix7 baseline but is not in ROUTE_F_FIX8_FILES.  This is the same fail-closed guard
that fixed the 2d8b8bab… packaging bug in fix1 and has been retained through fix2..
fix7, so a modified header can never again be silently reverted.

Each tarball is self-contained: a top directory holding the changed files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten.

stdlib only.  Run with:  python3 scripts/package_iq_rf_loopback_fix8.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_iq_rf_loopback_fix7.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_iq_rf_loopback_fix7"

PATCH_NAME = "sdr_rml23_live_iq_rf_loopback_fix8_patch"
PATCH_SUMS_NAME = "IQ_RF_LOOPBACK_FIX8_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_rf_loopback_fix8"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# fix8 files, relative to the repo root.  New files carried in full; modified files
# as fix7 baseline + fix8.
ROUTE_F_FIX8_FILES = [
    # Task A (TX/RX clip split) -- MODIFIED
    "board_package/iq_digital_loopback_sync.hpp",          # MODIFIED (SyncFidelityMetrics.clipped split + rails)
    "board_package/iq_digital_loopback_runner.hpp",        # MODIFIED (log output tx/rx clip fields)
    "board_package/iq_rf_loopback.hpp",                    # MODIFIED (RF_TX_CLIPPED / RF_RX_CLIPPED tokens)
    "board_package/iq_rf_loopback_report.hpp",             # MODIFIED (3-window NC summary scalars)
    "board_package/iq_rf_loopback_runner.hpp",             # MODIFIED (Task A metrics + Task B transient)
    # Task B (negative-control transient) -- MODIFIED
    "board_package/iq_rf_loopback_transfer.hpp",           # MODIFIED (discard refill + 3 noise windows)
    "sdr_adapter/pluto_device.hpp",                        # MODIFIED (tx_running() + RF echo hooks)
    "sdr_adapter/pluto_device_libiio.cpp",                 # MODIFIED (tx_running() impl)
    # Task C (RF level sweep) -- NEW
    "board_package/iq_rf_loopback_level_sweep.hpp",        # NEW (RF safe operating point sweep)
    "host_tests/test_iq_rf_loopback_level_sweep.cpp",      # NEW (host sweep test)
    # Task D (Route D artifact audit) -- NEW
    "scripts/audit_route_d_artifacts.py",                  # NEW (Route D frozen-artifact audit)
    # Task E (Route D2 4ASK verdict) -- MODIFIED
    "scripts/analyze_route_d2_4ask.py",                    # MODIFIED (compute_verdict + D2 artifacts)
    # Task F (D-vs-D2 A/B gate) -- NEW
    "board_package/iq_rf_loopback_ab.hpp",                 # NEW (pure 6-gate A/B gate)
    "host_tests/test_iq_rf_loopback_ab.cpp",               # NEW (host gate test)
    # wiring -- MODIFIED
    "board_package/board_gate9_full_chain_rml23.cpp",      # MODIFIED (sweep + ab phases)
    "board_package/gate9_phase.hpp",                       # MODIFIED (level-sweep + ab phase names)
    "host_tests/test_iq_rf_loopback.cpp",                  # MODIFIED (Task A/B test updates)
    "host_tests/build_host_tests.sh",                      # MODIFIED (build sweep + ab tests)
    "host_tests/run_tests.sh",                             # MODIFIED (run sweep + ab tests)
    # packaging + record -- NEW
    "scripts/package_iq_rf_loopback_fix8.py",              # NEW (this packager)
    "docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX8_AUDIT.md",  # NEW (audit + record)
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
    """Prevent a 'modified header silently reverted to fix7 baseline' bug.

    Walk the transitive #include closure of every fix8 C/C++ file.  For each
    resolved header whose bytes DIFFER from the fix7 baseline (or which does not
    exist in the baseline at all), require it to be in ROUTE_F_FIX8_FILES --
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

    fix8_set = set(ROUTE_F_FIX8_FILES)
    violations = set()
    seen = set()
    queue = [rel for rel in ROUTE_F_FIX8_FILES if rel.endswith(_CPP_EXT)]

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
                if sha256_of(resolved) != base_sha[rrel] and rrel not in fix8_set:
                    violations.add(rrel)
            else:
                # header present in working tree but absent from baseline
                if rrel not in fix8_set:
                    violations.add(rrel)
            if resolved not in seen:
                queue.append(rrel)

    return sorted(violations)


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    for rel in ROUTE_F_FIX8_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    work = tempfile.mkdtemp(prefix="pkg_rfloop_fix8_")
    try:
        # ---- extract baseline once ----
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- dependency-closure audit (fail-closed, before any package is built) ----
        violations = audit_dependency_closure(base)
        if violations:
            print("dependency-closure audit FAILED: the following working-tree "
                  "headers differ from the fix7 baseline (or are absent from it) "
                  "but are NOT listed in ROUTE_F_FIX8_FILES:", file=sys.stderr)
            for v in violations:
                print("  " + v, file=sys.stderr)
            print("Add them to ROUTE_F_FIX8_FILES so the merged package carries their "
                  "working-tree content.", file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK (all changed headers covered by ROUTE_F_FIX8_FILES)")

        # ---- 1. fix8 patch (fix8 only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_F_FIX8_FILES:
            copy_from_root(p, rel)
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: fix7 baseline + fix8 ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in ROUTE_F_FIX8_FILES:
            copy_from_root(full, rel)
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix8 patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (fix7 + fix8)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-32s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix8 patch", p_tar, p_n),
            ("merged full (fix7 + fix8)", full_tar, full_n),
        ]:
            print("  %-32s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
