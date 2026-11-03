#!/usr/bin/env python3
"""Package the RML23 Stage G synthetic-IQ injection phase as an independent patch
plus the merged full board package (diag_errata_39e5 baseline + Stage G).

Produces, under dist/ (leaving the already-shipped diag_errata / integrated_live_rx /
heartbeat / UI / live-rx / correctness packages untouched):

  1. sdr_rml23_live_synthetic_iq_patch.tar.gz          (Stage G only)
  2. sdr_rml23_live_board_package_synthetic_iq.tar.gz  (baseline + Stage G)

The Stage G patch is relative to the SAME baseline as the diag_errata_39e5 merged
package (sdr_rml23_live_board_package_diag_errata_39e5.tar.gz).  Stage G adds six
new files and modifies four existing files; the modified files are carried with
their FULL working-tree content (baseline + Stage G), so each patch stays
self-contained.  No shared-file stripping is needed because the diag_errata round
is complete and merged; Stage G touches no file that any other live patch owns.

Each tarball is self-contained: a top directory holding the changed files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten
(the new names are fresh).

stdlib only.  Run with:  python3 scripts/package_synthetic_iq.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_diag_errata_39e5.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_diag_errata_39e5"

PATCH_NAME = "sdr_rml23_live_synthetic_iq_patch"
PATCH_SUMS_NAME = "SYNTHETIC_IQ_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_synthetic_iq"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# Stage G files, relative to the repo root.  Every one is copied verbatim from the
# working tree (new files in full; modified files as baseline + Stage G).
STAGE_G_FILES = [
    "board_package/synthetic_iq_generator.hpp",
    "board_package/synthetic_iq_runner.hpp",
    "board_package/gate9_phase.hpp",
    "board_package/board_gate9_full_chain_rml23.cpp",
    "host_tests/test_synthetic_iq_generator.cpp",
    "host_tests/test_synthetic_iq_runner.cpp",
    "host_tests/build_host_tests.sh",
    "host_tests/run_tests.sh",
    "scripts/extract_radioml_stage_g.py",
    "scripts/verify_radioml_stage_g.py",
    "scripts/run_gate9_rml23.sh",
    "docs/M29_RML23_STAGE_G_SYNTHETIC_IQ_INJECTION_AUDIT.md",
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
    for rel in STAGE_G_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    work = tempfile.mkdtemp(prefix="pkg_syniq_")
    try:
        # ---- extract baseline once ----
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- 1. synthetic-iq patch (Stage G only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in STAGE_G_FILES:
            copy_from_root(p, rel)
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: baseline + Stage G ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in STAGE_G_FILES:
            copy_from_root(full, rel)
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("synthetic-iq patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (base+G)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-22s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("synthetic-iq patch", p_tar, p_n),
            ("merged full (base+G)", full_tar, full_n),
        ]:
            print("  %-22s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("                      %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
