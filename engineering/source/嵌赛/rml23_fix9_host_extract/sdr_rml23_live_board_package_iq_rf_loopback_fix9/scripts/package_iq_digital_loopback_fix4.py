#!/usr/bin/env python3
"""Package the RML23 Stage H-E / Route E fix4 (fix the fix3 sweep diagnostic
instrument WITHOUT changing the production chain) as an independent patch plus
the merged full board package.

fix4 is the diagnostic-instrument correctness increment on top of the already
shipped fix3 package (sdr_rml23_live_board_package_iq_digital_loopback_fix3.tar.gz,
sha f3128a68…).  fix3's own amplitude-sweep discriminator was what misjudged the
board's ~ -24 dB raw-container loss as "ambiguous":

  * it never propagated kind/target_rms into the sweep levels;
  * format_convert_raw_to_host unconditionally masked a fully-defined 12-bit
    right-justified negative (-32 = 0xFFE0) to a false +4064 RMS/clip;
  * it compared TX/RX counts directly without the TX-16-bit vs RX-12-bit signed
    full scale.

fix4 corrects those three defects and re-derives the root cause through a
COUNT-domain vs NORMALIZED-domain discriminator:

  count_gain_db      = 20 log10(rx_count_rms / tx_count_rms)   (raw container)
  normalized_gain_db = 20 log10((rx_count/2^(rx_bits-1)) / (tx_count/2^(tx_bits-1)))

so the sweep can now tell apart, in strict A->G order:
  * DIGITAL_LOOPBACK_COUNT_DOMAIN_SCALE   (normalized ~0 dB, count matches bit width)
  * DIGITAL_LOOPBACK_FIXED_ATTENUATION    (normalized << 0 dB, level-independent)
  * DIGITAL_LOOPBACK_FORMAT_MISALIGNMENT  (a non-reported shift recovers shape+scale)
  * DIGITAL_LOOPBACK_LIBIIO_CONVERT_SEMANTICS (libiio RX convert != host mirror)
  * DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN    (corr/floor/clip/consistency guard)

The encoding stage never pre-bakes COUNT_DOMAIN_SCALE as proven; only a board run
(normalized ~0 dB AND corr >= 0.9 AND no clip AND multi-level linear AND
libiio == host mirror) may confirm it.  DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN is
never promoted to PROVEN by a host test.

It touches NOTHING outside Stage H-E: no model / labels / golden / production
preprocessing / production read_rx default libiio path / RTL / XDC / bitstream /
Flash; no Stage G A/B/C/D semantics; no digital/rf/ambient/live-rx semantics.
It adds NO new default signed override and does not recommend --rx-format-signed=1.

Produces, under dist/ (leaving every earlier package untouched, INCLUDING the fix3
package it builds on):

  1. sdr_rml23_live_iq_digital_loopback_fix4_patch.tar.gz         (Route E fix4 only)
  2. sdr_rml23_live_board_package_iq_digital_loopback_fix4.tar.gz (fix3 full + fix4)

The fix4 patch is relative to the fix3 merged package (f3128a68…).  The merged full
is that fix3 package + the fix4 files.  Modified files are carried with their FULL
working-tree content (fix3 baseline + fix4), so the patch is self-contained.

A dependency-closure audit (audit_dependency_closure) walks the transitive #include
closure of every fix4 C/C++ file and ABORTS if any resolved header differs from the
fix3 baseline but is not in ROUTE_E_FIX4_FILES.  This is the same fail-closed guard
that fixed the 2d8b8bab… packaging bug in fix1 and has been retained through fix2
and fix3, so a modified header can never again be silently reverted to baseline.

Each tarball is self-contained: a top directory holding the changed files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten.

stdlib only.  Run with:  python3 scripts/package_iq_digital_loopback_fix4.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_iq_digital_loopback_fix3.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_iq_digital_loopback_fix3"

PATCH_NAME = "sdr_rml23_live_iq_digital_loopback_fix4_patch"
PATCH_SUMS_NAME = "IQ_DIGITAL_LOOPBACK_FIX4_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_digital_loopback_fix4"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# fix4 files, relative to the repo root.  New files carried in full; modified files
# as fix3 baseline + fix4.
ROUTE_E_FIX4_FILES = [
    "sdr_adapter/pluto_device.hpp",                          # MODIFIED (corrected convert mirror + rx_convert_raw_libiio)
    "sdr_adapter/pluto_device_libiio.cpp",                   # MODIFIED (LibiioDevice::rx_convert_raw_libiio)
    "board_package/iq_digital_loopback_sweep.hpp",           # MODIFIED (count/normalized dual-domain + A->G classifier)
    "board_package/board_gate9_full_chain_rml23.cpp",        # MODIFIED (run_iq_digital_loopback_sweep evidence prints)
    "board_package/iq_digital_loopback_runner.hpp",          # MODIFIED (tx-scale domain fields)
    "board_package/iq_digital_loopback_transfer.hpp",        # MODIFIED (TransferResult domain fields + scale_waveform clip)
    "host_tests/test_iq_digital_loopback_sweep.cpp",         # MODIFIED (14 scenarios + waveform/shift-search tests)
    "scripts/analyze_iq_digital_loopback_sweep.py",          # MODIFIED (fix4 dual-domain independent re-derivation)
    "scripts/package_iq_digital_loopback_fix4.py",           # NEW (this packager)
    "docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_FIX4_AUDIT.md",  # NEW (audit + record)
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
    """Prevent a 'modified header silently reverted to fix3 baseline' bug.

    Walk the transitive #include closure of every fix4 C/C++ file.  For each
    resolved header whose bytes DIFFER from the fix3 baseline (or which does not
    exist in the baseline at all), require it to be in ROUTE_E_FIX4_FILES --
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

    fix4_set = set(ROUTE_E_FIX4_FILES)
    violations = set()
    seen = set()
    queue = [rel for rel in ROUTE_E_FIX4_FILES if rel.endswith(_CPP_EXT)]

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
                if sha256_of(resolved) != base_sha[rrel] and rrel not in fix4_set:
                    violations.add(rrel)
            else:
                # header present in working tree but absent from baseline
                if rrel not in fix4_set:
                    violations.add(rrel)
            if resolved not in seen:
                queue.append(rrel)

    return sorted(violations)


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    for rel in ROUTE_E_FIX4_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    work = tempfile.mkdtemp(prefix="pkg_iqdloop_fix4_")
    try:
        # ---- extract baseline once ----
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- dependency-closure audit (fail-closed, before any package is built) ----
        violations = audit_dependency_closure(base)
        if violations:
            print("dependency-closure audit FAILED: the following working-tree "
                  "headers differ from the fix3 baseline (or are absent from it) "
                  "but are NOT listed in ROUTE_E_FIX4_FILES:", file=sys.stderr)
            for v in violations:
                print("  " + v, file=sys.stderr)
            print("Add them to ROUTE_E_FIX4_FILES so the merged package carries their "
                  "working-tree content.", file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK (all changed headers covered by ROUTE_E_FIX4_FILES)")

        # ---- 1. fix4 patch (fix4 only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_E_FIX4_FILES:
            copy_from_root(p, rel)
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: fix3 baseline + fix4 ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in ROUTE_E_FIX4_FILES:
            copy_from_root(full, rel)
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix4 patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (fix3 + fix4)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-32s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix4 patch", p_tar, p_n),
            ("merged full (fix3 + fix4)", full_tar, full_n),
        ]:
            print("  %-32s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
