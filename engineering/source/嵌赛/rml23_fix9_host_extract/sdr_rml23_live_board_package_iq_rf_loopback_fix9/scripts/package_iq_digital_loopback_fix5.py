#!/usr/bin/env python3
"""Package the RML23 Stage H-E / Route E fix5 (arbitrary-cyclic-IQ full-period
synchronization + scale-independent fidelity judgment) as an independent patch
plus the merged full board package.

fix5 is the synchronization/fidelity-judgment increment on top of the already
shipped fix4 package (sdr_rml23_live_board_package_iq_digital_loopback_fix4.tar.gz,
sha 48334de2…).  fix4's amplitude-sweep discriminator proved the TX/RX format and
the COUNT-domain scale, but its *per-file* fidelity judgment still used a bounded
integer delay search in [0, delay_margin) that cannot cover the full 53760-sample
cyclic period, and it computed NMSE/EVM against the TX energy, so a low correlation
could still print a low EVM.  fix5 corrects both and adds a TX DMA payload proof.

fix5 replaces the bounded-delay search with an FFT circular cross-correlation over
ALL P circular shifts of one full period:

    c[k] = | h[k] + h[nfft - P + k] |,  h = IFFT( FFT(x_pad) · conj(FFT(y_pad)) )
    c[k] = | Σ_j x[j] · conj(y[(j - k) mod P]) |            (exact, P need not be pow2)

and re-derives fidelity scale-independently with the optimal complex gain a:

    a = Σ y·conj(x) / Σ |x|²
    normalized_residual = ||y − a·x||² / ||y||²   (= 1 − |corr|², denominator is RX)

so a 1/16 count-domain scale is normalized away (×16 for TX16/RX12), and a low
correlation can never again print a low EVM.  New per-file judgment tokens, in
strict order:

    TX_DMA_PAYLOAD_MISMATCH  (sha of the actual bytes handed to iio_buffer_push)
    CAPTURE_TOO_SHORT
    CIRCULAR_SYNC_AMBIGUOUS
    DIGITAL_LOOPBACK_DISTORTS_IQ    (corr < 0.9)
    DIGITAL_LOOPBACK_PRESERVES_IQ   (corr >= 0.9 AND no clip AND normalized gain ok
                                     AND nmse_evm_consistent)
    DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN

Only when every frozen file reaches PRESERVES_IQ does the runner run the 24-class
classification; otherwise it reports INVALID_DUE_TO_FIDELITY_GATE.  A host test can
never promote DIGITAL_LOOPBACK_CAPABILITY_NOT_PROVEN to PROVEN.

It touches NOTHING outside Stage H-E: no model / labels / golden / production
preprocessing / production read_rx default libiio path / RTL / XDC / bitstream /
Flash; no Stage G A/B/C/D semantics; no digital/rf/ambient/live-rx semantics.

Produces, under dist/ (leaving every earlier package untouched, INCLUDING the fix4
package it builds on):

  1. sdr_rml23_live_iq_digital_loopback_fix5_patch.tar.gz         (Route E fix5 only)
  2. sdr_rml23_live_board_package_iq_digital_loopback_fix5.tar.gz (fix4 full + fix5)

The fix5 patch is relative to the fix4 merged package (48334de2…).  The merged full
is that fix4 package + the fix5 files.  Modified files are carried with their FULL
working-tree content (fix4 baseline + fix5), so the patch is self-contained.

A dependency-closure audit (audit_dependency_closure) walks the transitive #include
closure of every fix5 C/C++ file and ABORTS if any resolved header differs from the
fix4 baseline but is not in ROUTE_E_FIX5_FILES.  This is the same fail-closed guard
that fixed the 2d8b8bab… packaging bug in fix1 and has been retained through fix2,
fix3 and fix4, so a modified header can never again be silently reverted to baseline.

Each tarball is self-contained: a top directory holding the changed files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten.

stdlib only.  Run with:  python3 scripts/package_iq_digital_loopback_fix5.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_iq_digital_loopback_fix4.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_iq_digital_loopback_fix4"

PATCH_NAME = "sdr_rml23_live_iq_digital_loopback_fix5_patch"
PATCH_SUMS_NAME = "IQ_DIGITAL_LOOPBACK_FIX5_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_digital_loopback_fix5"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# fix5 files, relative to the repo root.  New files carried in full; modified files
# as fix4 baseline + fix5.
ROUTE_E_FIX5_FILES = [
    "board_package/iq_digital_loopback_sync.hpp",           # NEW (FFT circular sync + scale-independent fidelity)
    "board_package/iq_digital_loopback_transfer.hpp",       # MODIFIED (capture 2P+guard + TX DMA payload SHA)
    "board_package/iq_digital_loopback_runner.hpp",         # MODIFIED (verdict gating + aligned_rx classification)
    "sdr_adapter/pluto_device.hpp",                         # MODIFIED (tx_dma_payload_sha + corrupt hook)
    "sdr_adapter/pluto_device_libiio.cpp",                  # MODIFIED (LibiioDevice::tx_dma_payload_sha)
    "host_tests/test_iq_digital_loopback_sync.cpp",         # NEW (15 sync/fidelity host tests)
    "host_tests/build_host_tests.sh",                       # MODIFIED (register sync test build)
    "host_tests/run_tests.sh",                              # MODIFIED (register sync test run)
    "scripts/package_iq_digital_loopback_fix5.py",          # NEW (this packager)
    "docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_FIX5_AUDIT.md",  # NEW (audit + record)
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
    """Prevent a 'modified header silently reverted to fix4 baseline' bug.

    Walk the transitive #include closure of every fix5 C/C++ file.  For each
    resolved header whose bytes DIFFER from the fix4 baseline (or which does not
    exist in the baseline at all), require it to be in ROUTE_E_FIX5_FILES --
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

    fix5_set = set(ROUTE_E_FIX5_FILES)
    violations = set()
    seen = set()
    queue = [rel for rel in ROUTE_E_FIX5_FILES if rel.endswith(_CPP_EXT)]

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
                if sha256_of(resolved) != base_sha[rrel] and rrel not in fix5_set:
                    violations.add(rrel)
            else:
                # header present in working tree but absent from baseline
                if rrel not in fix5_set:
                    violations.add(rrel)
            if resolved not in seen:
                queue.append(rrel)

    return sorted(violations)


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    for rel in ROUTE_E_FIX5_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    work = tempfile.mkdtemp(prefix="pkg_iqdloop_fix5_")
    try:
        # ---- extract baseline once ----
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- dependency-closure audit (fail-closed, before any package is built) ----
        violations = audit_dependency_closure(base)
        if violations:
            print("dependency-closure audit FAILED: the following working-tree "
                  "headers differ from the fix4 baseline (or are absent from it) "
                  "but are NOT listed in ROUTE_E_FIX5_FILES:", file=sys.stderr)
            for v in violations:
                print("  " + v, file=sys.stderr)
            print("Add them to ROUTE_E_FIX5_FILES so the merged package carries their "
                  "working-tree content.", file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK (all changed headers covered by ROUTE_E_FIX5_FILES)")

        # ---- 1. fix5 patch (fix5 only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_E_FIX5_FILES:
            copy_from_root(p, rel)
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: fix4 baseline + fix5 ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in ROUTE_E_FIX5_FILES:
            copy_from_root(full, rel)
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix5 patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (fix4 + fix5)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-32s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix5 patch", p_tar, p_n),
            ("merged full (fix4 + fix5)", full_tar, full_n),
        ]:
            print("  %-32s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
