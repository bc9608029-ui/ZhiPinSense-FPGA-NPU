#!/usr/bin/env python3
"""Package the M29 RML23 LIVE-RX diagnostic errata 39e5 (Stages C/D/E + hard
requirements #1/#2/#3/#4/#9/#11) as an independent patch plus the merged full
board package, relative to the integrated-live-rx baseline.

Produces, under dist/ (leaving every previously shipped package untouched):

  1. sdr_rml23_live_diagnostic_errata_39e5_patch.tar.gz   (the 22-file diff)
  2. sdr_rml23_live_board_package_diag_errata_39e5.tar.gz (baseline + diff)

The baseline is sdr_rml23_live_board_package_integrated_live_rx.tar.gz (the
A+B+C merged package).  The patch carries exactly the files that differ from
that baseline (board runtime + host tests + docs + analysis/compare tools), so
it is an independent, self-contained diff that overlays the shipped baseline.

Each tarball is self-contained: a top directory holding the files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist_hist/ or any
frozen package (cb3f204e/e988707c/e166bb32/…/5167649b) is overwritten.

Frozen identities are NOT touched (model json/raw, params_md5, bitstream,
deployment_golden, contracts, RTL/XDC/Flash): those paths are absent from both
the changed and added lists below.

stdlib only.  Run with:  python3 scripts/package_diagnostic_errata_39e5.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_integrated_live_rx.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_integrated_live_rx"

PATCH_NAME = "sdr_rml23_live_diagnostic_errata_39e5_patch"
PATCH_SUMS_NAME = "DIAGNOSTIC_ERRATA_39E5_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_diag_errata_39e5"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# ---- changed files (exist in baseline, overwritten from the working tree) ----
CHANGED = [
    "board_package/board_gate9_full_chain_rml23.cpp",   # #3 ctl server + capture + logits export
    "board_package/board_ui_live_rml23.cpp",            # #4 UI freshness
    "board_package/chain_common.hpp",                   # #1 PreScaleCapture + #10 model_scale comment
    "board_package/npu_classifier24.hpp",               # #2 input-transfer audit
    "board_package/result_frame_v2_parse.hpp",          # #3(d) state version param
    "host_tests/build_host_tests.sh",                   # new test build lines
    "host_tests/run_tests.sh",                          # new test run lines
    "host_tests/test_chain_common.cpp",                 # #1 test_pre_scale_capture
    "scripts/start_all_rml23.sh",                       # #11 dedup + effective config print
    "sdr_adapter/resampler.hpp",                        # #1 out_index/current_phase
    "ui_sw/ui_render.cpp",                              # #4 new status render mapping
    "ui_sw/ui_render.hpp",                              # #4 Status enum extension
]

# ---- added files (absent from baseline, new in this errata) ------------------
ADDED = [
    "board_package/capture_hook.hpp",                   # Stage C atomic tensor capture
    "board_package/logits_export.hpp",                  # Stage E board logits export
    "docs/M29_RML23_LIVE_RX_DIAGNOSTIC_ERRATA_39e5_AUDIT.md",
    "host_tests/test_capture_hook.cpp",                 # Stage C test
    "host_tests/test_control_socket_process.cpp",       # #3 control-server test
    "host_tests/test_tx_audit_rml23.cpp",               # #9 TX A/B test
    "host_tests/test_ui_live_rx_process.cpp",           # #4 UI process test
    "scripts/analyze_live_rx_capture.py",               # Stage D analysis tool
    "scripts/compare_three_backends.py",                # Stage E three-backend compare
    "scripts/export_fp32_onnx.py",                      # Stage E fp32 ONNX export
]


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
        p = os.path.join(stage, rel.replace("/", os.sep))
        lines.append("%s *%s\n" % (sha256_of(p), rel))
    with open(os.path.join(stage, sums_name), "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(sorted(lines)))
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

    work = tempfile.mkdtemp(prefix="pkg_diag39e5_")
    try:
        # ---- extract baseline once ----
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- 1. independent patch (the diff) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in CHANGED + ADDED:
            copy_from_root(p, rel)
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: baseline + diff ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in CHANGED + ADDED:
            copy_from_root(full, rel)
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("diag errata patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full 39e5", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-18s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("diag errata patch", p_tar, p_n),
            ("merged full 39e5", full_tar, full_n),
        ]:
            print("  %-18s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("                    %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
