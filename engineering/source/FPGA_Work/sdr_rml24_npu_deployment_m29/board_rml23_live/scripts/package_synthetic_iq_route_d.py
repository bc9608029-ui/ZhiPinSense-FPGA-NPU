#!/usr/bin/env python3
"""Package the RML23 Stage G route D (RadioML round-trip preprocess) as an
independent patch plus the merged full board package.

Route D is a Stage G追加硬要求 on top of the already-shipped A/B/C synthetic-IQ
injection (sdr_rml23_live_board_package_synthetic_iq.tar.gz, sha 6c3258a7…).  It adds
the production-receive round-trip attribution instrument and touches NOTHING outside
Stage G (no model / labels / golden / RTL / bitstream / Flash, no A/B/C semantics).

Produces, under dist/ (leaving the A/B/C synthetic-iq packages and every earlier
package untouched):

  1. sdr_rml23_live_synthetic_iq_route_d_patch.tar.gz         (route D only)
  2. sdr_rml23_live_board_package_synthetic_iq_route_d.tar.gz (synthetic-iq + D)

The route D patch is relative to the synthetic-iq merged package (6c3258a7…).
The merged full is that synthetic-iq package + the route D files.  Modified files are
carried with their FULL working-tree content (synthetic-iq baseline + route D), so the
patch is self-contained.

Each tarball is self-contained: a top directory holding the changed files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten.

stdlib only.  Run with:  python3 scripts/package_synthetic_iq_route_d.py
"""

import gzip
import hashlib
import os
import shutil
import sys
import tarfile
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DIST = os.path.join(ROOT, "dist")
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_synthetic_iq.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_synthetic_iq"

PATCH_NAME = "sdr_rml23_live_synthetic_iq_route_d_patch"
PATCH_SUMS_NAME = "SYNTHETIC_IQ_ROUTE_D_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_synthetic_iq_route_d"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# Route D files, relative to the repo root.  New files carried in full; modified
# files as synthetic-iq baseline + route D.
ROUTE_D_FILES = [
    "board_package/synthetic_iq_roundtrip.hpp",        # NEW
    "board_package/board_gate9_full_chain_rml23.cpp",  # MODIFIED (route D dispatch)
    "host_tests/test_synthetic_iq_roundtrip.cpp",      # NEW
    "host_tests/build_host_tests.sh",                  # MODIFIED (+roundtrip target)
    "host_tests/run_tests.sh",                         # MODIFIED (+roundtrip run)
    "scripts/analyze_roundtrip_stage_g.py",            # NEW
    "scripts/run_gate9_rml23.sh",                      # MODIFIED (route D usage)
    "docs/M29_RML23_STAGE_G_SYNTHETIC_IQ_INJECTION_AUDIT.md",  # MODIFIED (route D)
]


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


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    for rel in ROUTE_D_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    work = tempfile.mkdtemp(prefix="pkg_syniq_d_")
    try:
        # ---- extract baseline once ----
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- 1. route D patch (route D only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_D_FILES:
            copy_from_root(p, rel)
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: synthetic-iq baseline + route D ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in ROUTE_D_FILES:
            copy_from_root(full, rel)
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("route D patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (synthetic-iq + D)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-32s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("route D patch", p_tar, p_n),
            ("merged full (synthetic-iq + D)", full_tar, full_n),
        ]:
            print("  %-32s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
