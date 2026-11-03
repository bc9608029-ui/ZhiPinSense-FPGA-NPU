#!/usr/bin/env python3
"""Package RML23 Route F fix9r1 -- the fix9r packaging-permission correction.

fix9r (sdr_rml23_live_board_package_iq_rf_loopback_fix9r.tar.gz, sha 3642caffac4d…)
is the Route F "per-file recovery" increment and is CORRECT in content.  Its ONLY
defect is packaging-level: the tar member mode for every file was written as
`-rw-rw-rw-` (0666) because the fix9r packager's make_tar() relied on
tarfile.gettarinfo(), which on Windows reports the on-disk (read-only-flag-only)
mode -- i.e. 0666 for everything -- instead of an explicit Unix mode.  On the board
that means `scripts/*.sh` and `board_package/*.sh` are not executable and the
board-side `./scripts/build_on_board.sh` step fails with "Permission denied".

fix9r1 fixes NOTHING in the RF algorithm and resumes NOTHING of the paused fix10
(double-SDR).  It re-packs the fix9r content with an EXPLICIT tar member mode:

    directories                   -> 0o755
    *.sh (scripts/board_package/…) -> 0o755
    everything else               -> 0o644

plus it writes the correct mode into the tar member metadata (not just a chmod in
the working tree), keeps uid=0/gid=0/uname="" /gname="" /mtime=0, and a gzip header
with mtime=0 and no FNAME.  Directory members are now emitted explicitly (the fix9r
tarball had none), each 0755.  0666 / 0777 are never used.

Content is byte-identical to fix9r EXCEPT two newly-added files (this packager and
the fix9r1 audit doc) -- the delivery manifest and the memory index live outside the
package.  Every one of the 569 fix9r content files is verified byte-identical below.

Produces, under dist/ (leaving the fix9r packages and every earlier package
untouched):

  1. sdr_rml23_live_iq_rf_loopback_fix9r1_patch.tar.gz          (fix9r1 only)
  2. sdr_rml23_live_board_package_iq_rf_loopback_fix9r1.tar.gz  (fix9r full + fix9r1)

stdlib only.  Run with:  python3 scripts/package_iq_rf_loopback_fix9r1.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_iq_rf_loopback_fix9r.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_iq_rf_loopback_fix9r"
BASE_SHA = "3642caffac4d9b0da3876d88b44b0643e6a2d63e7332535dba1f7959060cc337"

PATCH_NAME = "sdr_rml23_live_iq_rf_loopback_fix9r1_patch"
PATCH_SUMS_NAME = "IQ_RF_LOOPBACK_FIX9R1_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_rf_loopback_fix9r1"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# fix9r1 adds exactly two files on top of fix9r.  Both land in directories that
# already exist in the fix9r full tree (scripts/, docs/), so no new top-level dir.
FIX9R1_NEW_FILES = [
    "scripts/package_iq_rf_loopback_fix9r1.py",                  # this packager
    "docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX9R1_AUDIT.md",  # fix9r1 audit + record
]


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_bytes(path, data, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    os.chmod(path, mode)


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
    write_bytes(os.path.join(stage, sums_name), "".join(sorted(lines)).encode("utf-8"))
    return len(rels)


def make_tar(stage, tar_path):
    """Deterministic tar.gz with EXPLICIT member modes (dir/.sh -> 0755, else 0644).

    The fix9r packager's make_tar left info.mode untouched, which on Windows made
    every member 0666.  Here every member's mode is assigned explicitly from the
    file kind (never 0666/0777), and directory members are emitted explicitly.
    """
    top = os.path.basename(stage.rstrip("/\\"))
    raw = tar_path + ".tmp.tar"

    entries = [("", True)]  # top-level directory member, 0755
    for dirpath, dirnames, filenames in os.walk(stage):
        dirnames.sort()
        filenames.sort()
        for d in dirnames:
            entries.append((os.path.relpath(os.path.join(dirpath, d), stage).replace(os.sep, "/"), True))
        for name in filenames:
            entries.append((os.path.relpath(os.path.join(dirpath, name), stage).replace(os.sep, "/"), False))
    entries.sort(key=lambda e: e[0])

    with tarfile.open(raw, "w", format=tarfile.GNU_FORMAT) as t:
        for rel, is_dir in entries:
            if rel == "":
                full = stage
                arc = top
            else:
                full = os.path.join(stage, rel.replace("/", os.sep))
                arc = os.path.join(top, rel).replace(os.sep, "/")
            info = t.gettarinfo(full, arcname=arc)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            if is_dir:
                info.mode = 0o755
            elif rel.endswith(".sh"):
                info.mode = 0o755
            else:
                info.mode = 0o644
            if is_dir:
                t.addfile(info)
            else:
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


def verify_content_consistency(base, full):
    """Prove fix9r1 content == fix9r content except the 2 new files + SUMS.

    Returns (unchanged, changed, extra) where changed must be empty and extra must
    be exactly FIX9R1_NEW_FILES.  SHA256SUMS.txt is regenerated, so it is excluded
    from the byte-compare (its fix9r1 content legitimately lists 2 more files).
    """
    def walk(folder):
        out = {}
        for dirpath, dirnames, filenames in os.walk(folder):
            dirnames.sort()
            for name in filenames:
                rel = os.path.relpath(os.path.join(dirpath, name), folder).replace(os.sep, "/")
                out[rel] = sha256_of(os.path.join(dirpath, name))
        return out

    base_map = walk(base)
    full_map = walk(full)

    unchanged = []
    changed = []
    for rel in sorted(base_map):
        if rel == "SHA256SUMS.txt":
            continue
        if rel not in full_map:
            changed.append((rel, "MISSING"))
        elif full_map[rel] != base_map[rel]:
            changed.append((rel, "DIFFER"))
        else:
            unchanged.append(rel)
    extra = sorted(set(full_map) - set(base_map))
    return unchanged, changed, extra


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    actual = sha256_of(BASE_TAR)
    if actual != BASE_SHA:
        sys.exit("baseline package SHA mismatch:\n  expected %s\n  got      %s" % (BASE_SHA, actual))

    for rel in FIX9R1_NEW_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    work = tempfile.mkdtemp(prefix="pkg_rfloop_fix9r1_")
    try:
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- clean full tree: fix9r full + the 2 fix9r1-only files ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in FIX9R1_NEW_FILES:
            src = os.path.join(ROOT, rel)
            with open(src, "rb") as f:
                write_bytes(os.path.join(full, rel.replace("/", os.sep)), f.read())

        # ---- content-consistency proof (byte-identical except 2 new files) ----
        unchanged, changed, extra = verify_content_consistency(base, full)
        if changed:
            print("content-consistency FAILED: fix9r files differ in fix9r1:", file=sys.stderr)
            for rel, why in changed:
                print("  %s (%s)" % (rel, why), file=sys.stderr)
            sys.exit(1)
        if extra != sorted(FIX9R1_NEW_FILES):
            print("content-consistency FAILED: unexpected extra files in fix9r1:", file=sys.stderr)
            for rel in extra:
                print("  " + rel, file=sys.stderr)
            sys.exit(1)
        print("content-consistency: OK (%d fix9r files byte-identical, +2 fix9r1 files)" % len(unchanged))

        # ---- 1. fix9r1 patch (fix9r1 only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in FIX9R1_NEW_FILES:
            src = os.path.join(ROOT, rel)
            with open(src, "rb") as f:
                write_bytes(os.path.join(p, rel.replace("/", os.sep)), f.read())
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: fix9r full + fix9r1 ----
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix9r1 patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (fix9r + fix9r1)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-32s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix9r1 patch", p_tar, p_n),
            ("merged full (fix9r + fix9r1)", full_tar, full_n),
        ]:
            print("  %-32s %d content-files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
