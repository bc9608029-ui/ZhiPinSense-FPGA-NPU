#!/usr/bin/env python3
"""Package the RML23 Stage H-E / Route E fix3 (digital-loopback ~20 dB amplitude-loss
diagnosis + repair) as an independent patch plus the merged full board package.

fix3 is the coding increment on top of the already-shipped fix2 package
(sdr_rml23_live_board_package_iq_digital_loopback_fix2.tar.gz, sha c841cee4…).  It
adds the amplitude-sweep diagnostic instrument that discriminates the four possible
sources of the ~16x (~20 dB) loss seen on board (rms_tx ~ 9.52 counts vs rms_rx ~
0.728-0.848 counts, all RX_LOW_AMPLITUDE), which fix2 could not separate:

  * libiio convert semantics      -> DIGITAL_LOOPBACK_LIBIIO_CONVERT_SEMANTICS
  * 12-bit shift / HDL bit align  -> DIGITAL_LOOPBACK_FORMAT_MISALIGNMENT
  * fixed loopback gain           -> DIGITAL_LOOPBACK_FIXED_ATTENUATION
  * none of these                 -> DIGITAL_LOOPBACK_UNITY / NOT_PROVEN

It adds:
  * iq_digital_loopback_sweep.hpp: deterministic tone/ramp/PRBS sweep at logical RMS
    8..512 counts, raw-vs-logical gain discriminator, rx-shift correction search,
    and test-fixture scale auto-selection (16..128 counts, zero clip);
  * board gate phase --phase=iq-digital-loopback-sweep + runner flags
    --digital-loopback-tx-scale / --rx-format-shift / --tx-format-shift / --rx-bits /
    --tx-bits;
  * the format-override path on the real device (set_tx/rx_data_format_override),
    which lets the board test a corrected shift WITHOUT recompiling, by switching the
    convert path to the host mirror with the overridden format;
  * the format_convert_host_to_raw sign-extension fix (host-mirror correctness; a
    no-op for the real board's shift=4, so production data-path semantics are
    unchanged);
  * the host sweep test + a separate analyzer that INDEPENDENTLY re-derives the root
    cause and cross-checks the board's token.

It touches NOTHING outside Stage H-E: no model / labels / golden / RTL / bitstream /
Flash; no Stage G A/B/C/D semantics; no digital/rf/ambient/live-rx semantics.

Produces, under dist/ (leaving every earlier package untouched, INCLUDING the fix2
package it builds on):

  1. sdr_rml23_live_iq_digital_loopback_fix3_patch.tar.gz         (Route E fix3 only)
  2. sdr_rml23_live_board_package_iq_digital_loopback_fix3.tar.gz (fix2 full + fix3)

The fix3 patch is relative to the fix2 merged package (c841cee4…).  The merged full
is that fix2 package + the fix3 files.  Modified files are carried with their FULL
working-tree content (fix2 baseline + fix3), so the patch is self-contained.

A dependency-closure audit (audit_dependency_closure) walks the transitive #include
closure of every fix3 C/C++ file and ABORTS if any resolved header differs from the
fix2 baseline but is not in ROUTE_E_FIX3_FILES.  This is the same fail-closed guard
that fixed the 2d8b8bab… packaging bug in fix1 and was retained through fix2, so a
modified header can never again be silently reverted to baseline.

Each tarball is self-contained: a top directory holding the changed files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten.

stdlib only.  Run with:  python3 scripts/package_iq_digital_loopback_fix3.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_iq_digital_loopback_fix2.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_iq_digital_loopback_fix2"

PATCH_NAME = "sdr_rml23_live_iq_digital_loopback_fix3_patch"
PATCH_SUMS_NAME = "IQ_DIGITAL_LOOPBACK_FIX3_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_digital_loopback_fix3"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# fix3 files, relative to the repo root.  New files carried in full; modified files
# as fix2 baseline + fix3.
ROUTE_E_FIX3_FILES = [
    "board_package/iq_digital_loopback_sweep.hpp",          # NEW (sweep instrument + classifier)
    "sdr_adapter/pluto_device.hpp",                         # MODIFIED (format_convert_host_to_raw sign-extension + overrides)
    "sdr_adapter/pluto_device_libiio.cpp",                  # MODIFIED (format override path + tx_raw_after_inverse)
    "board_package/board_gate9_full_chain_rml23.cpp",       # MODIFIED (run_iq_digital_loopback_sweep)
    "board_package/gate9_phase.hpp",                        # MODIFIED (valid_phase += iq-digital-loopback-sweep)
    "board_package/iq_digital_loopback_runner.hpp",         # MODIFIED (tx-scale + format shift/bits overrides)
    "board_package/iq_digital_loopback_transfer.hpp",       # MODIFIED (transfer_one_file tx_scale + pre/post evidence)
    "board_package/board_common.hpp",                       # MODIFIED (opt_i64)
    "host_tests/test_iq_digital_loopback_sweep.cpp",        # NEW (8 sweep tests, 50 asserts)
    "host_tests/build_host_tests.sh",                       # MODIFIED (+sweep target)
    "host_tests/run_tests.sh",                              # MODIFIED (+run sweep)
    "scripts/analyze_iq_digital_loopback_sweep.py",         # NEW (independent re-derivation analyzer)
    "scripts/package_iq_digital_loopback_fix3.py",          # NEW (this packager)
    "docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_FIX3_AUDIT.md",  # NEW (audit + record)
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
    """Prevent a 'modified header silently reverted to fix2 baseline' bug.

    Walk the transitive #include closure of every fix3 C/C++ file.  For each
    resolved header whose bytes DIFFER from the fix2 baseline (or which does not
    exist in the baseline at all), require it to be in ROUTE_E_FIX3_FILES --
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

    fix3_set = set(ROUTE_E_FIX3_FILES)
    violations = set()
    seen = set()
    queue = [rel for rel in ROUTE_E_FIX3_FILES if rel.endswith(_CPP_EXT)]

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
                if sha256_of(resolved) != base_sha[rrel] and rrel not in fix3_set:
                    violations.add(rrel)
            else:
                # header present in working tree but absent from baseline
                if rrel not in fix3_set:
                    violations.add(rrel)
            if resolved not in seen:
                queue.append(rrel)

    return sorted(violations)


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    for rel in ROUTE_E_FIX3_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    work = tempfile.mkdtemp(prefix="pkg_iqdloop_fix3_")
    try:
        # ---- extract baseline once ----
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- dependency-closure audit (fail-closed, before any package is built) ----
        violations = audit_dependency_closure(base)
        if violations:
            print("dependency-closure audit FAILED: the following working-tree "
                  "headers differ from the fix2 baseline (or are absent from it) "
                  "but are NOT listed in ROUTE_E_FIX3_FILES:", file=sys.stderr)
            for v in violations:
                print("  " + v, file=sys.stderr)
            print("Add them to ROUTE_E_FIX3_FILES so the merged package carries their "
                  "working-tree content.", file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK (all changed headers covered by ROUTE_E_FIX3_FILES)")

        # ---- 1. fix3 patch (fix3 only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_E_FIX3_FILES:
            copy_from_root(p, rel)
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: fix2 baseline + fix3 ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in ROUTE_E_FIX3_FILES:
            copy_from_root(full, rel)
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix3 patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (fix2 + fix3)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-32s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix3 patch", p_tar, p_n),
            ("merged full (fix2 + fix3)", full_tar, full_n),
        ]:
            print("  %-32s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
