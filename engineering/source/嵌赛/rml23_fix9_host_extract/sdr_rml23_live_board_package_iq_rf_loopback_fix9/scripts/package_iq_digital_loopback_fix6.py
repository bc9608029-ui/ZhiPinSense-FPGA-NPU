#!/usr/bin/env python3
"""Package the RML23 Stage H-E / Route E fix6 (waveform-fidelity / circular-origin
split + classification-window selection) as an independent patch plus the merged
full board package.

fix6 is the fidelity-judgment refinement on top of the already shipped fix5 package
(sdr_rml23_live_board_package_iq_digital_loopback_fix5.tar.gz, sha 8239285c…).  fix5
replaced the bounded delay search with an FFT circular cross-correlation over ALL P
shifts and re-derived fidelity scale-independently.  fix6 corrects what fix5 got
wrong about *periodic / self-similar* waveforms, per the six requirements:

  (1) "waveform fidelity" and "circular-origin uniqueness" become two SEPARATE
      conclusions (sync_origin vs the fidelity verdict);
  (2) the fixed peak_ratio >= 2 gate is REMOVED as a PRESERVES_IQ prerequisite;
  (3) the TX's own circular autocorrelation r_norm[k] (circular_autocorr_norm) is
      computed to explain the inherent sidelobes of a clean loopback:
      c[k] ~= corr_peak * r_norm[(k - peak) mod P];
  (4) PRESERVES_IQ = corr >= 0.9 AND normalized_residual consistent AND no clipping
      AND DMA payload SHA correct (the DMA SHA gate lives in the runner);
  (5) a competing lobe that does NOT exceed the autocorrelation prediction is an
      EQUIVALENT circular origin (same waveform under a different labeled origin),
      reported as sync_origin=AMBIGUOUS_EQUIVALENT -- NEVER as waveform distortion;
  (6) only an UNEXPLAINED competing lobe (corr_k > predicted + margin, i.e. a
      genuinely DIFFERENT waveform that also correlates) is CIRCULAR_SYNC_AMBIGUOUS;
  (7) the classification window is selected by aligning the naive decimated stream
      against the Route D recovered_tensor (roundtrip_manifest.tsv column 9), which
      is the correctly-aligned [2,1024] reference, instead of trusting two naive
      per-file frames that can straddle the zero-guard / cyclic boundary.

The origin classification in circular_sync: for every corr lobe within 10% of the
peak (kCompetingRatio = 0.9, a RELATIVE threshold -- an absolute corr>=0.9 gate would
make the "unexplained competing lobe" case mathematically unreachable, since two
independent components cannot both reach absolute corr>=0.9), the predicted sidelobe
is peak_corr * r_norm[delta]; if corr_k > predicted + kPeakExplainAbsMargin (0.1) the
lobe is UNEXPLAINED else EQUIVALENT.  origin = Ambiguous if any unexplained lobe,
else Equivalent if any competing lobe, else Unique.

New per-file judgment tokens (observation-only, never a PASS gate):

    INSUFFICIENT_EVIDENCE  (rx < 1024 complex)
    CAPTURE_TOO_SHORT
    RX_ALL_ZERO
    RX_LOW_AMPLITUDE       (rms_rx < 2.0 counts)
    CIRCULAR_SYNC_AMBIGUOUS        (origin == Ambiguous, an unexplained lobe)
    DIGITAL_LOOPBACK_DISTORTS_IQ   (corr < 0.9)
    DIGITAL_LOOPBACK_PRESERVES_IQ  (corr >= 0.9 AND no clip AND normalized gain ok
                                    AND nmse_evm_consistent)
    DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN

plus the independent sync_origin report IQ_DIGITAL_LOOPBACK_SYNC_ORIGIN (UNIQUE /
AMBIGUOUS_EQUIVALENT / CIRCULAR_SYNC_AMBIGUOUS) and the classification-window report
IQ_DIGITAL_LOOPBACK_WINDOW (delay_offset / tensor_corr / tensor_nmse / sha_equal).

It touches NOTHING outside Stage H-E: no model / labels / golden / production
preprocessing / production read_rx default libiio path / RTL / XDC / bitstream /
Flash; no Stage G A/B/C/D semantics; no digital/rf/ambient/live-rx semantics.

Produces, under dist/ (leaving every earlier package untouched, INCLUDING the fix5
package it builds on):

  1. sdr_rml23_live_iq_digital_loopback_fix6_patch.tar.gz         (Route E fix6 only)
  2. sdr_rml23_live_board_package_iq_digital_loopback_fix6.tar.gz (fix5 full + fix6)

The fix6 patch is relative to the fix5 merged package (8239285c…).  The merged full
is that fix5 package + the fix6 files.  Modified files are carried with their FULL
working-tree content (fix5 baseline + fix6), so the patch is self-contained.

A dependency-closure audit (audit_dependency_closure) walks the transitive #include
closure of every fix6 C/C++ file and ABORTS if any resolved header differs from the
fix5 baseline but is not in ROUTE_E_FIX6_FILES.  This is the same fail-closed guard
that fixed the 2d8b8bab… packaging bug in fix1 and has been retained through fix2,
fix3, fix4 and fix5, so a modified header can never again be silently reverted.

Each tarball is self-contained: a top directory holding the changed files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten.

stdlib only.  Run with:  python3 scripts/package_iq_digital_loopback_fix6.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_iq_digital_loopback_fix5.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_iq_digital_loopback_fix5"

PATCH_NAME = "sdr_rml23_live_iq_digital_loopback_fix6_patch"
PATCH_SUMS_NAME = "IQ_DIGITAL_LOOPBACK_FIX6_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_digital_loopback_fix6"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# fix6 files, relative to the repo root.  New files carried in full; modified files
# as fix5 baseline + fix6.
ROUTE_E_FIX6_FILES = [
    "board_package/iq_digital_loopback_sync.hpp",           # MODIFIED (autocorr + origin split + fix6 verdict)
    "board_package/iq_digital_loopback.hpp",                # MODIFIED (recovered tensor + window selection)
    "board_package/iq_digital_loopback_runner.hpp",         # MODIFIED (sync-origin + window report, fix6 gating)
    "host_tests/test_iq_digital_loopback_sync.cpp",         # MODIFIED (origin/autocorr/window tests)
    "host_tests/test_iq_digital_loopback.cpp",              # MODIFIED (recovered_file sidecar round-trip)
    "scripts/package_iq_digital_loopback_fix6.py",          # NEW (this packager)
    "docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_FIX6_AUDIT.md",  # NEW (audit + record)
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
    """Prevent a 'modified header silently reverted to fix5 baseline' bug.

    Walk the transitive #include closure of every fix6 C/C++ file.  For each
    resolved header whose bytes DIFFER from the fix5 baseline (or which does not
    exist in the baseline at all), require it to be in ROUTE_E_FIX6_FILES --
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

    fix6_set = set(ROUTE_E_FIX6_FILES)
    violations = set()
    seen = set()
    queue = [rel for rel in ROUTE_E_FIX6_FILES if rel.endswith(_CPP_EXT)]

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
                if sha256_of(resolved) != base_sha[rrel] and rrel not in fix6_set:
                    violations.add(rrel)
            else:
                # header present in working tree but absent from baseline
                if rrel not in fix6_set:
                    violations.add(rrel)
            if resolved not in seen:
                queue.append(rrel)

    return sorted(violations)


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    for rel in ROUTE_E_FIX6_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    work = tempfile.mkdtemp(prefix="pkg_iqdloop_fix6_")
    try:
        # ---- extract baseline once ----
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- dependency-closure audit (fail-closed, before any package is built) ----
        violations = audit_dependency_closure(base)
        if violations:
            print("dependency-closure audit FAILED: the following working-tree "
                  "headers differ from the fix5 baseline (or are absent from it) "
                  "but are NOT listed in ROUTE_E_FIX6_FILES:", file=sys.stderr)
            for v in violations:
                print("  " + v, file=sys.stderr)
            print("Add them to ROUTE_E_FIX6_FILES so the merged package carries their "
                  "working-tree content.", file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK (all changed headers covered by ROUTE_E_FIX6_FILES)")

        # ---- 1. fix6 patch (fix6 only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_E_FIX6_FILES:
            copy_from_root(p, rel)
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: fix5 baseline + fix6 ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in ROUTE_E_FIX6_FILES:
            copy_from_root(full, rel)
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix6 patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (fix5 + fix6)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-32s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix6 patch", p_tar, p_n),
            ("merged full (fix5 + fix6)", full_tar, full_n),
        ]:
            print("  %-32s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
