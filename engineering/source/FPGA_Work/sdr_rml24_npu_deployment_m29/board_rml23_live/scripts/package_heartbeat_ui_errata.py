#!/usr/bin/env python3
"""Package the RML23 heartbeat errata + UI redesign as two independent patches
plus a merged full board package.

Produces, under dist/:

  1. sdr_rml23_live_heartbeat_errata_patch.tar.gz   (Task A only)
  2. sdr_rml23_live_ui_redesign_patch.tar.gz        (Task B only)
  3. sdr_rml23_live_board_package_integrated.tar.gz (baseline + A + B)

Each tarball is self-contained: a top directory holding the changed files plus
a SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b),
so `cd <topdir> && sha256sum -c <SUMS>` verifies it.  The three tarballs are
left untouched where they overlap; nothing in dist_hist/ or any frozen package
is overwritten.

stdlib only.  Run with:  python3 scripts/package_heartbeat_ui_errata.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_correctness_fix.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_correctness_fix"

HB_PATCH_NAME = "sdr_rml23_live_heartbeat_errata_patch"
HB_SUMS_NAME = "HEARTBEAT_ERRATA_PATCH_SHA256SUMS.txt"
UI_PATCH_NAME = "sdr_rml23_live_ui_redesign_patch"
UI_SUMS_NAME = "UI_REDESIGN_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_integrated"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# ---- Task A (heartbeat) source files, full content from the working tree ----
TASK_A_FILES = [
    "board_package/board_gate9_full_chain_rml23.cpp",
    "board_package/board_ui_live_rml23.cpp",
    "board_package/ui_state_map.hpp",
    "sdr_adapter/unix_socket_sink.hpp",
    "ui_sw/direct_framebuffer_backend.cpp",
    "ui_sw/direct_framebuffer_backend.hpp",
    "host_tests/test_heartbeat_socket.cpp",
]

# ---- Task B (UI) source files, full content from the working tree ----------
TASK_B_FILES = [
    "ui_sw/font_atlas.cpp",
    "ui_sw/font_atlas.hpp",
    "ui_sw/ui_layout.hpp",
    "ui_sw/ui_render.cpp",
    "host_tests/test_ui_layout_m19.cpp",
    "host_tests/test_ui_boundary.cpp",
    "host_tests/make_ui_rml23_snapshots.cpp",
    "host_tests/make_ui_bbox_debug.cpp",
    "host_tests/_snap_rml23.sh",
    "host_tests/_diff_ui_snapshots.py",
    "host_tests/_task_b_delta.sh",
    "host_tests/_baseline_ui.sh",
    "host_tests/_ui_redesign.sh",
    "host_tests/_width_probe.cpp",
    "host_tools/ppm2png.py",
    "docs/M29_RML23_UI_DESIGN_SPEC.md",
    "docs/M29_RML23_UI_REDESIGN_AUDIT.md",
]

# The two shared build/run scripts are present in BOTH tasks.  Each patch gets
# the baseline script plus ONLY its own test line, so the two patches stay
# logically independent.  The merged full package carries the real merged
# working-tree version.
SHARED_BUILD = "host_tests/build_host_tests.sh"
SHARED_RUN = "host_tests/run_tests.sh"


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path):
    with open(path, "r", encoding="utf-8", newline="\n") as f:
        return f.read()


def write_text(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.chmod(path, mode)


# ---- derive per-patch shared scripts from the baseline (correctness) --------
def make_hb_build(base):
    block = ('echo "== build test_heartbeat_socket =="\n'
             '$CXX $FLAGS test_heartbeat_socket.cpp -o bin/test_heartbeat_socket\n\n')
    i = base.index('echo "build_host_tests.sh: OK')
    s = base[:i] + block + base[i:]
    return s.replace("test_golden_rml23}", "test_golden_rml23,test_heartbeat_socket}")


def make_ui_build(base):
    block = ('echo "== build test_ui_boundary =="\n'
             '$CXX $FLAGS test_ui_boundary.cpp ../ui_sw/font_atlas.cpp '
             '../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/test_ui_boundary\n\n')
    i = base.index('echo "build_host_tests.sh: OK')
    s = base[:i] + block + base[i:]
    return s.replace("test_golden_rml23}", "test_golden_rml23,test_ui_boundary}")


def make_hb_run(base):
    i = base.index("./test_board_build.sh")
    return base[:i] + "./bin/test_heartbeat_socket    || rc=1\n" + base[i:]


def make_ui_run(base):
    i = base.index("./bin/test_rf_fix_rml23")
    return base[:i] + "./bin/test_ui_boundary         || rc=1\n" + base[i:]


def copy_from_root(stage, rel):
    src = os.path.join(ROOT, rel)
    dst = os.path.join(stage, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def copy_file(src, dst):
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
    """Re-extract the tarball and check every hash, returning (ok, count)."""
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

    work = tempfile.mkdtemp(prefix="pkg_hbui_")
    try:
        # ---- extract baseline once ----
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        base_build = read_text(os.path.join(base, SHARED_BUILD))
        base_run = read_text(os.path.join(base, SHARED_RUN))

        # ---- 1. heartbeat patch ----
        hb = os.path.join(work, HB_PATCH_NAME)
        os.makedirs(hb, exist_ok=True)
        for rel in TASK_A_FILES:
            copy_from_root(hb, rel)
        write_text(os.path.join(hb, SHARED_BUILD), make_hb_build(base_build), 0o755)
        write_text(os.path.join(hb, SHARED_RUN), make_hb_run(base_run), 0o755)
        hb_n = write_sums(hb, HB_SUMS_NAME)
        hb_tar = os.path.join(DIST, HB_PATCH_NAME + ".tar.gz")
        make_tar(hb, hb_tar)
        shutil.copy2(os.path.join(hb, HB_SUMS_NAME), os.path.join(DIST, HB_SUMS_NAME))

        # ---- 2. UI patch ----
        ui = os.path.join(work, UI_PATCH_NAME)
        os.makedirs(ui, exist_ok=True)
        for rel in TASK_B_FILES:
            copy_from_root(ui, rel)
        write_text(os.path.join(ui, SHARED_BUILD), make_ui_build(base_build), 0o755)
        write_text(os.path.join(ui, SHARED_RUN), make_ui_run(base_run), 0o755)
        ui_n = write_sums(ui, UI_SUMS_NAME)
        ui_tar = os.path.join(DIST, UI_PATCH_NAME + ".tar.gz")
        make_tar(ui, ui_tar)
        shutil.copy2(os.path.join(ui, UI_SUMS_NAME), os.path.join(DIST, UI_SUMS_NAME))

        # ---- 3. merged full package: baseline + A + B + merged shared scripts ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in TASK_A_FILES + TASK_B_FILES:
            copy_from_root(full, rel)
        # real merged build/run scripts from the working tree
        copy_from_root(full, SHARED_BUILD)
        copy_from_root(full, SHARED_RUN)
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("heartbeat patch", hb_tar, HB_SUMS_NAME, HB_PATCH_NAME),
            ("UI patch", ui_tar, UI_SUMS_NAME, UI_PATCH_NAME),
            ("merged full", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-16s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("heartbeat patch", hb_tar, hb_n),
            ("UI patch", ui_tar, ui_n),
            ("merged full", full_tar, full_n),
        ]:
            print("  %-16s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("                  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
