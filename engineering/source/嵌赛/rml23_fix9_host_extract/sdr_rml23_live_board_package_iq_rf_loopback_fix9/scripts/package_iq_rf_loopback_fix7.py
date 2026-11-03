#!/usr/bin/env python3
"""Package the RML23 Stage H-F / Route F fix7 as an independent patch plus the
merged full board package.

fix7 is built on top of the shipped fix6 package
(sdr_rml23_live_board_package_iq_digital_loopback_fix6.tar.gz, sha 713c93b4…).  It
is the Stage H-F ("Route F") increment: a PHYSICAL TX->RX RF self-loopback plus a
Route D2 non-training 4ASK ablation, plus a memory/total-gate fix.  Three mutually
isolated subtasks:

  Task A -- memory + total-gate fix
    * The per-file summary no longer retains the large buffers.  sync.aligned_rx is
      2P int16 (~215 KB/file); retaining it across 240 files is ~51 MiB and trips the
      M22 RSS-growth gate.  push_file_summary / push_rf_file_summary swap aligned_rx
      to an empty vector BEFORE the move, so the retained summary keeps only scalars +
      short SHAs and the per-file loop reuses one freed block (RSS stays bounded).
      Applied to BOTH the digital runner (iq_digital_loopback_runner.hpp) and the new
      RF runner (iq_rf_loopback_report.hpp).
    * The total GATE now folds classification into functional_pass: infra_ok ∧
      fidelity_ok ∧ classification_ok.  classification_ok is true unless the run's
      classification was UNATTRIBUTABLE (no global calibration, fidelity-blocked, or
      zero classified frames) -- accuracy itself is measurement-only and never
      PASS/FAIL.  The M22 verdict is folded on top in board_gate9_full_chain_rml23.cpp
      (finish_m22_runtime), so an M22 FAIL forces GATE=FAIL too.  No RSS threshold is
      raised or disabled.

  Task B -- Route F physical RF self-loop
    * New phase `--phase=iq-rf-loopback` (a DISTINCT name, never reusing
      "iq-digital-loopback"): loopback=0 with read-back confirmation,
      --rf-path=direct-cable, --tx-atten=-40 (the kSafeTxCeilingDb ceiling, never
      raised), --rx-gain=<value>, 50-ohm SMA coax direct connect, no antenna /
      amplifier, no auto TX-power increase, and a DeviceStateGuard that RAII
      saves/restores every device parameter.
    * A TX-off NEGATIVE CONTROL is captured before TX-on (per-file noise-floor
      evidence for the SNR judgment and railed-RX detection), and per-file records
      carry TX verify / TX-DMA payload SHA / refill / buffer-lifecycle / loopback
      read-back / attenuator read-back evidence.
    * RF fidelity tokens (observation-only): RF_PATH_NOT_PROVEN / RF_RX_ALL_ZERO /
      RF_RX_TOO_LOW / RF_RX_CLIPPED / RF_SYNC_NOT_FOUND / RF_DISTORTS_IQ /
      RF_PRESERVES_IQ, judged with the fix6 full-period FFT circular sync
      (scale-independent residual/EVM/corr/CFO) plus the noise-floor SNR.
    * Classification NEVER uses a per-file reference gain as an oracle: the ONLY
      amplitude/phase correction the classifier sees is ONE global fixed complex gain
      estimated from an independent calibration subset (--rf-calib-count=N).  A
      per-file best-fit gain is measurement-only.

  Task C -- Route D2 non-training 4ASK ablation
    * scripts/analyze_route_d2_4ask.py: D0 (per-file RMS baseline) vs D1 (single
      global K) vs D2 (D1 + preserve the signal's own DC) vs D3 (edge/guard/K grid),
      with the global K chosen ONLY from unlabelled reconstruction error /
      quantisation utilisation / clip rate on a fixed calibration subset and held
      fixed on an independent holdout.  It never retrains, never runs the NPU, and
      never issues an accuracy PASS.  If even the reconstruction evidence cannot
      separate 4ASK from D0, the verdict is NON_RETRAINING_4ASK_FIX_NOT_PROVEN.

It touches NOTHING outside Stage H-F / Route F + Route D2: no model / labels / golden
/ production preprocessing / production read_rx default libiio path / RTL / XDC /
bitstream / Flash; no Stage G A/B/C/D semantics; no digital/rf/ambient/live-rx
semantics; no fix6 artifact is overwritten.

Produces, under dist/ (leaving every earlier package untouched, INCLUDING the fix6
package it builds on):

  1. sdr_rml23_live_iq_rf_loopback_fix7_patch.tar.gz          (Route F + D2 fix7 only)
  2. sdr_rml23_live_board_package_iq_rf_loopback_fix7.tar.gz  (fix6 full + fix7)

The fix7 patch is relative to the fix6 merged package (713c93b4…).  The merged full
is that fix6 package + the fix7 files.  Modified files are carried with their FULL
working-tree content (fix6 baseline + fix7), so the patch is self-contained.

A dependency-closure audit (audit_dependency_closure) walks the transitive #include
closure of every fix7 C/C++ file and ABORTS if any resolved header differs from the
fix6 baseline but is not in ROUTE_F_FIX7_FILES.  This is the same fail-closed guard
that fixed the 2d8b8bab… packaging bug in fix1 and has been retained through fix2,
fix3, fix4, fix5 and fix6, so a modified header can never again be silently reverted.

Each tarball is self-contained: a top directory holding the changed files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten.

stdlib only.  Run with:  python3 scripts/package_iq_rf_loopback_fix7.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_iq_digital_loopback_fix6.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_iq_digital_loopback_fix6"

PATCH_NAME = "sdr_rml23_live_iq_rf_loopback_fix7_patch"
PATCH_SUMS_NAME = "IQ_RF_LOOPBACK_FIX7_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_rf_loopback_fix7"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# fix7 files, relative to the repo root.  New files carried in full; modified files
# as fix6 baseline + fix7.
ROUTE_F_FIX7_FILES = [
    # Task A (memory + total gate) -- MODIFIED
    "board_package/iq_digital_loopback_runner.hpp",         # MODIFIED (push_file_summary memory sink)
    # Task B (physical RF self-loop) -- MODIFIED + NEW
    "board_package/board_gate9_full_chain_rml23.cpp",       # MODIFIED (--phase=iq-rf-loopback + M22 fold)
    "board_package/gate9_phase.hpp",                        # MODIFIED (new phase name)
    "sdr_adapter/pluto_device.hpp",                         # MODIFIED (loopback read-back + RF echo hooks)
    "board_package/iq_rf_loopback.hpp",                     # NEW (pure-logic RF fidelity / global gain)
    "board_package/iq_rf_loopback_report.hpp",              # NEW (per-file summary + memory sink)
    "board_package/iq_rf_loopback_transfer.hpp",            # NEW (per-file RF transfer, board+host verbatim)
    "board_package/iq_rf_loopback_runner.hpp",              # NEW (board orchestration)
    "host_tests/test_iq_rf_loopback.cpp",                   # NEW (host RF test)
    "host_tests/build_host_tests.sh",                       # MODIFIED (build test_iq_rf_loopback)
    "host_tests/run_tests.sh",                              # MODIFIED (run test_iq_rf_loopback)
    # Task C (Route D2 4ASK ablation) -- NEW
    "scripts/analyze_route_d2_4ask.py",                     # NEW (D0/D1/D2/D3 non-training ablation)
    # packaging + record -- NEW
    "scripts/package_iq_rf_loopback_fix7.py",               # NEW (this packager)
    "docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX7_AUDIT.md",  # NEW (audit + record)
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
    """Prevent a 'modified header silently reverted to fix6 baseline' bug.

    Walk the transitive #include closure of every fix7 C/C++ file.  For each
    resolved header whose bytes DIFFER from the fix6 baseline (or which does not
    exist in the baseline at all), require it to be in ROUTE_F_FIX7_FILES --
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

    fix7_set = set(ROUTE_F_FIX7_FILES)
    violations = set()
    seen = set()
    queue = [rel for rel in ROUTE_F_FIX7_FILES if rel.endswith(_CPP_EXT)]

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
                if sha256_of(resolved) != base_sha[rrel] and rrel not in fix7_set:
                    violations.add(rrel)
            else:
                # header present in working tree but absent from baseline
                if rrel not in fix7_set:
                    violations.add(rrel)
            if resolved not in seen:
                queue.append(rrel)

    return sorted(violations)


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    for rel in ROUTE_F_FIX7_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    work = tempfile.mkdtemp(prefix="pkg_rfloop_fix7_")
    try:
        # ---- extract baseline once ----
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- dependency-closure audit (fail-closed, before any package is built) ----
        violations = audit_dependency_closure(base)
        if violations:
            print("dependency-closure audit FAILED: the following working-tree "
                  "headers differ from the fix6 baseline (or are absent from it) "
                  "but are NOT listed in ROUTE_F_FIX7_FILES:", file=sys.stderr)
            for v in violations:
                print("  " + v, file=sys.stderr)
            print("Add them to ROUTE_F_FIX7_FILES so the merged package carries their "
                  "working-tree content.", file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK (all changed headers covered by ROUTE_F_FIX7_FILES)")

        # ---- 1. fix7 patch (fix7 only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_F_FIX7_FILES:
            copy_from_root(p, rel)
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: fix6 baseline + fix7 ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in ROUTE_F_FIX7_FILES:
            copy_from_root(full, rel)
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix7 patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (fix6 + fix7)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-32s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix7 patch", p_tar, p_n),
            ("merged full (fix6 + fix7)", full_tar, full_n),
        ]:
            print("  %-32s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
