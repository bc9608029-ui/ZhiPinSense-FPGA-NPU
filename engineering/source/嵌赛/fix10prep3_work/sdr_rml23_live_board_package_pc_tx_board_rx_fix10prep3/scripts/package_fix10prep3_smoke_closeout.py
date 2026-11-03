#!/usr/bin/env python3
"""Package the fix10prep3 smoke-closeout delivery (post board smoke test).

Sits on top of the frozen board-tested canonical-frame full package and carries ONLY
the auditable delta introduced since then:

  * the 8-file 4ASK recovery diagnostic patch (additive observability — payload
    fractional-correlation fields, --dump-failed-rx, exact C++ replay tool; NO gate /
    threshold / model / weight / preprocess change), and
  * this smoke-closeout audit doc + this packager script.

Produces, under dist/ (NEVER overwrites the canonical-frame or 4ask-diag packages):
  1. sdr_rml23_fix10prep3_smoke_closeout_boardtest_full.tar.gz   (full tree)
  2. sdr_rml23_fix10prep3_smoke_closeout_patch.tar.gz            (delta onto canonical-full)

The patch is stored FLAT (files at tarball root: board_package/..., host_tests/...),
so overlaying it onto the extracted canonical-frame full tree reproduces the
smoke-closeout full tree byte-for-byte.  The packager proves this with a literal
byte-level overlay verification, not just a SHA-set audit.

Fail-closed audits run BEFORE anything is emitted:
  * RED-LINE headers (six recovery/frame/transfer headers) byte-identical to the
    canonical-frame full base.
  * PROTECTED dirs (model/weights/labels/preprocess/contracts) byte-identical to base.
  * canonical training components (3 CI16 + canonical header + embedded-data header)
    byte-identical to base.
  * every quoted include of every patched C++ file resolves inside the tree.
  * complete-delta: patch + canonical-full base == full tree.
  * patch self-containment: patch overlaid onto canonical-full ALONE resolves includes.
  * old-fix10 (external_rf / pluto_external) zero-residual.
  * literal patch-over-base overlay == full (byte-level).

Each tarball carries a SHA256SUMS in the repo's `HASH *relpath` convention
(sha256sum -b).  stdlib only; deterministic (uid/gid 0, mtime 0, sorted entries,
gzip level 9, mtime 0), and every tarball is built TWICE and byte-compared.
Run with:
    python scripts/package_fix10prep3_smoke_closeout.py
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

# The frozen board-tested source the smoke-closeout delta is defined against.
CANONICAL_FULL_TAR = os.path.join(
    DIST, "sdr_rml23_fix10prep3_canonical_frame_boardtest_full.tar.gz")

FULL_NAME = "sdr_rml23_live_board_package_pc_tx_board_rx_fix10prep3"
FULL_TAR_BASENAME = "sdr_rml23_fix10prep3_smoke_closeout_boardtest_full"
FULL_SUMS_NAME = "SHA256SUMS.txt"

PATCH_NAME = "sdr_rml23_fix10prep3_smoke_closeout_patch"
PATCH_SUMS_NAME = "SMOKE_CLOSEOUT_PATCH_SHA256SUMS.txt"

# ---- the smoke-closeout change set (the ONLY thing the patch carries) ----
# 8-file 4ASK recovery diagnostic patch + 2 smoke-closeout additions = 10 files.
PATCH_FILES = [
    "board_package/iq_dual_sdr_coarse_cfo_recovery.hpp",
    "board_package/iq_pc_tx_board_rx_23class_fix10.hpp",
    "host_tools/replay_fix10_failed_rx.cpp",
    "host_tests/build_host_tests.sh",
    "host_tests/run_tests.sh",
    "host_tests/test_iq_dual_sdr_23class_fix10.cpp",
    "docs/M29_RML23_FIX10PREP3_4ASK_RECOVERY_DIAGNOSTIC.md",
    "scripts/package_4ask_diag.sh",
    "docs/M29_RML23_FIX10PREP3_SMOKE_CLOSEOUT_AUDIT.md",
    "scripts/package_fix10prep3_smoke_closeout.py",
]
PATCH_SET = set(PATCH_FILES)

# Directories never packaged (build products / python cache / output).
EXCLUDED_DIRS = {"host_tests/bin", "host_tests/__pycache__", "host_tools/__pycache__",
                 "scripts/__pycache__", "dist", ".git",
                 "host_tools/.build_burst_cache", "results"}

# Transient files never packaged (stale host-test logs from a manual run).
EXCLUDED_FILES = {
    "host_tests/build_host_tests.log",
    "host_tests/run_tests.log",
}

# Directories whose contents must be byte-identical to the canonical-frame base (model
# / weights / labels / preprocess / mapping / gates untouched).
PROTECTED_DIRS = ("model_rml23/", "model_12class/", "contracts/",
                  "deployment_golden/")

# RED LINE: recovery core, frame math, transfer/provenance state machine, canonical-sync
# contract and baselines the fix10prep2 base proved; the smoke closeout must NOT touch them.
RED_LINE_HEADERS = (
    "board_package/iq_rf_sync_recovery.hpp",
    "board_package/iq_rf_training_frame.hpp",
    "board_package/iq_digital_loopback.hpp",
    "board_package/iq_pc_tx_board_rx_transfer_fix10.hpp",
    "board_package/iq_rf_fix9r_baseline.hpp",
    "board_package/iq_clean_baseline.hpp",
)

# The canonical training components frozen from aarch64 output — must stay byte-identical
# to the board-tested base (they are the cross-arch fix itself).
CANONICAL_COMPONENTS = (
    "contracts/fix10_canonical_frame_v1/preamble.ci16",
    "contracts/fix10_canonical_frame_v1/payload_training.ci16",
    "contracts/fix10_canonical_frame_v1/tail.ci16",
    "contracts/fix10_canonical_frame_v1/manifest.tsv",
    "contracts/fix10_canonical_frame_v1/SHA256SUMS.txt",
    "board_package/iq_fix10_canonical_frame.hpp",
    "board_package/iq_fix10_canonical_frame_data.hpp",
)

_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*"([^"]+)"')
_CPP_EXT = (".cpp", ".hpp", ".h", ".cc", ".cxx")


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
        dirnames[:] = sorted(
            d for d in dirnames
            if os.path.relpath(os.path.join(dirpath, d), stage).replace(os.sep, "/")
            not in EXCLUDED_DIRS)
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), stage).replace(os.sep, "/")
            if rel not in EXCLUDED_FILES:
                out.append(rel)
    return sorted(out)


def write_sums(stage, sums_name):
    rels = [r for r in list_files(stage) if r != sums_name]
    lines = ["%s *%s\n" % (sha256_of(os.path.join(stage, rel.replace("/", os.sep))), rel)
             for rel in rels]
    write_bytes(os.path.join(stage, sums_name), "".join(sorted(lines)).encode("utf-8"))
    return len(rels)


def _gzip(raw, tar_path):
    with open(raw, "rb") as fin:
        with gzip.GzipFile(filename="", mode="wb", fileobj=open(tar_path, "wb"),
                           compresslevel=9, mtime=0) as gz:
            shutil.copyfileobj(fin, gz)
    os.remove(raw)


def _entry_info(full, arc, is_dir):
    info = tarfile.TarInfo()
    info.name = arc
    st = os.lstat(full)
    info.size = 0 if is_dir else st.st_size
    info.mtime = 0
    info.mode = 0o755 if is_dir else (0o755 if arc.endswith(".sh") else 0o644)
    info.type = tarfile.DIRTYPE if is_dir else tarfile.REGTYPE
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def make_tar(stage, tar_path):
    """Full-tree tarball: single top directory == tree basename."""
    top = os.path.basename(stage.rstrip("/\\"))
    raw = tar_path + ".tmp.tar"

    entries = [("", True)]
    for dirpath, dirnames, filenames in os.walk(stage):
        dirnames[:] = sorted(
            d for d in dirnames
            if os.path.relpath(os.path.join(dirpath, d), stage).replace(os.sep, "/")
            not in EXCLUDED_DIRS)
        filenames.sort()
        for d in dirnames:
            entries.append((os.path.relpath(os.path.join(dirpath, d), stage)
                            .replace(os.sep, "/"), True))
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), stage).replace(os.sep, "/")
            if rel not in EXCLUDED_FILES:
                entries.append((rel, False))
    entries.sort(key=lambda e: e[0])

    with tarfile.open(raw, "w", format=tarfile.GNU_FORMAT) as t:
        for rel, is_dir in entries:
            full = stage if rel == "" else os.path.join(stage, rel.replace("/", os.sep))
            arc = top if rel == "" else os.path.join(top, rel).replace(os.sep, "/")
            info = _entry_info(full, arc, is_dir)
            if is_dir:
                t.addfile(info)
            else:
                with open(full, "rb") as f:
                    t.addfile(info, f)
    _gzip(raw, tar_path)


def make_tar_flat(stage, tar_path):
    """Patch tarball: files at root (board_package/..., host_tests/...), no top dir, so
    `tar -xzf patch -C <extracted-full-top>` overlays onto the full tree directly."""
    raw = tar_path + ".tmp.tar"

    entries = []
    for dirpath, dirnames, filenames in os.walk(stage):
        dirnames.sort()
        filenames.sort()
        for d in dirnames:
            entries.append((os.path.relpath(os.path.join(dirpath, d), stage)
                            .replace(os.sep, "/"), True))
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), stage).replace(os.sep, "/")
            entries.append((rel, False))
    entries.sort(key=lambda e: e[0])

    with tarfile.open(raw, "w", format=tarfile.GNU_FORMAT) as t:
        for rel, is_dir in entries:
            full = os.path.join(stage, rel.replace("/", os.sep))
            info = _entry_info(full, rel, is_dir)
            if is_dir:
                t.addfile(info)
            else:
                with open(full, "rb") as f:
                    t.addfile(info, f)
    _gzip(raw, tar_path)


def build_tar_deterministic(make_fn, stage, tar_path):
    r1 = tar_path + ".run1"
    r2 = tar_path + ".run2"
    make_fn(stage, r1)
    make_fn(stage, r2)
    with open(r1, "rb") as a, open(r2, "rb") as b:
        if a.read() != b.read():
            sys.exit("DETERMINISM FAILED: %s (two builds differ)" % tar_path)
    os.remove(r2)
    os.replace(r1, tar_path)


def verify_tar(tar_path, sums_name, topdir):
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(tar_path, "r:gz") as t:
            t.extractall(td, filter="data")
        d = os.path.join(td, topdir)
        ok = 0
        bad = 0
        with open(os.path.join(d, sums_name), "r", encoding="utf-8") as f:
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


def verify_tar_flat(tar_path, sums_name):
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(tar_path, "r:gz") as t:
            t.extractall(td, filter="data")
        ok = 0
        bad = 0
        with open(os.path.join(td, sums_name), "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line:
                    continue
                hx, _, rel = line.partition(" *")
                p = os.path.join(td, rel.replace("/", os.sep))
                if sha256_of(p) == hx:
                    ok += 1
                else:
                    bad += 1
                    print("  MISMATCH: %s" % rel, file=sys.stderr)
        return (bad == 0, ok + bad, ok)


def _cpp_includes(text):
    out = []
    for line in text.splitlines():
        m = _INCLUDE_RE.match(line)
        if m:
            out.append(m.group(1))
    return out


_INCLUDE_DIRS = ("board_package", "sdr_adapter", "ui_sw")


def audit_dependency_closure(full_dir, files=None, extra_roots=()):
    """Fail-closed: every quoted include of every audited C++ file must resolve to a
    real file inside `full_dir` (or one of `extra_roots`)."""
    if files is None:
        files = PATCH_FILES
    roots = (full_dir,) + tuple(extra_roots)

    by_base = {}
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(
                d for d in dirnames
                if os.path.relpath(os.path.join(dirpath, d), root).replace(os.sep, "/")
                not in EXCLUDED_DIRS)
            for name in filenames:
                if name.endswith(_CPP_EXT):
                    p = os.path.join(dirpath, name)
                    by_base.setdefault(name, []).append(p)

    missing = set()
    for rel in files:
        if not rel.endswith(_CPP_EXT):
            continue
        abs_path = os.path.join(full_dir, rel.replace("/", os.sep))
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            includes = _cpp_includes(f.read())
        for inc in includes:
            cands = [os.path.normpath(os.path.join(os.path.dirname(abs_path), inc))]
            for root in roots:
                cands += [os.path.normpath(os.path.join(root, d, inc))
                          for d in _INCLUDE_DIRS]
            if not any(os.path.exists(c) for c in cands):
                base = os.path.basename(inc)
                hits = by_base.get(base, [])
                if len(hits) != 1:
                    missing.add(rel + " -> " + inc)
    return sorted(missing)


def audit_complete_delta(full_dir, base_dir, patch_files):
    """Fail-closed: every file in the full tree is either byte-identical to the base, or
    carried by the patch -- i.e. patch + base reproduces the full tree."""
    patch_set = set(patch_files)
    violations = []
    for rel in list_files(full_dir):
        bf = os.path.join(base_dir, rel.replace("/", os.sep))
        ff = os.path.join(full_dir, rel.replace("/", os.sep))
        if os.path.exists(bf) and sha256_of(ff) == sha256_of(bf):
            continue
        if rel in patch_set:
            continue
        violations.append(rel)
    return sorted(violations)


def verify_protected_unchanged(full_dir, base_dir):
    violations = []
    for pdir in PROTECTED_DIRS:
        base_p = os.path.join(base_dir, pdir)
        full_p = os.path.join(full_dir, pdir)
        if not os.path.isdir(base_p):
            continue
        for dirpath, dirnames, filenames in os.walk(base_p):
            dirnames.sort()
            for name in sorted(filenames):
                bf = os.path.join(dirpath, name)
                rel = os.path.relpath(bf, base_dir).replace(os.sep, "/")
                ff = os.path.join(full_dir, rel.replace("/", os.sep))
                if not os.path.exists(ff) or sha256_of(ff) != sha256_of(bf):
                    violations.append(rel)
    return sorted(violations)


def verify_red_line_headers(full_dir, base_dir):
    violations = []
    for rel in RED_LINE_HEADERS:
        ff = os.path.join(full_dir, rel.replace("/", os.sep))
        bf = os.path.join(base_dir, rel.replace("/", os.sep))
        if not os.path.exists(bf):
            violations.append(rel + " (missing in base)")
        elif not os.path.exists(ff) or sha256_of(ff) != sha256_of(bf):
            violations.append(rel + " (differs from canonical-full base)")
    return sorted(violations)


def verify_canonical_components(full_dir, base_dir):
    violations = []
    for rel in CANONICAL_COMPONENTS:
        ff = os.path.join(full_dir, rel.replace("/", os.sep))
        bf = os.path.join(base_dir, rel.replace("/", os.sep))
        if not os.path.exists(bf):
            violations.append(rel + " (missing in base)")
        elif not os.path.exists(ff) or sha256_of(ff) != sha256_of(bf):
            violations.append(rel + " (differs from canonical-full base)")
    return sorted(violations)


def verify_patch_overlay(base_dir, patch_dir, full_dir):
    """Literal byte-level proof that overlaying the patch onto the canonical-full base
    reproduces the full tree: copy base, overlay patch files, then every content file
    byte-matches the full staging (ignoring only the derived root SHA256SUMS.txt)."""
    over = os.path.join(os.path.dirname(full_dir), "_overlay")
    shutil.copytree(base_dir, over)
    for rel in PATCH_FILES:
        src = os.path.join(patch_dir, rel.replace("/", os.sep))
        dst = os.path.join(over, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    full_rels = set(r for r in list_files(full_dir) if r != FULL_SUMS_NAME)
    over_rels = set(r for r in list_files(over) if r != FULL_SUMS_NAME)
    viol = []
    if full_rels != over_rels:
        viol.append("file-set mismatch: only-full=%s only-overlay=%s" %
                    (sorted(full_rels - over_rels), sorted(over_rels - full_rels)))
    for rel in sorted(full_rels & over_rels):
        if sha256_of(os.path.join(full_dir, rel)) != \
           sha256_of(os.path.join(over, rel)):
            viol.append(rel)
    return viol


def _fail(label, violations):
    print(label + " FAILED:", file=sys.stderr)
    for v in violations:
        print("  " + v, file=sys.stderr)
    sys.exit(1)


def main():
    for rel in PATCH_FILES:
        if not os.path.exists(os.path.join(ROOT, rel.replace("/", os.sep))):
            sys.exit("missing smoke-closeout file: %s" % rel)
    if not os.path.exists(CANONICAL_FULL_TAR):
        sys.exit("missing canonical-frame full base: %s" % CANONICAL_FULL_TAR)

    work = tempfile.mkdtemp(prefix="pkg_smoke_closeout_")
    try:
        # ---- base = extracted canonical-frame full (frozen board-tested source) ----
        base_x = os.path.join(work, "base")
        os.makedirs(base_x)
        with tarfile.open(CANONICAL_FULL_TAR, "r:gz") as t:
            t.extractall(base_x, filter="data")
        base_ref = os.path.join(base_x, FULL_NAME)
        if not os.path.isdir(base_ref):
            sys.exit("canonical-full base missing top dir %s" % FULL_NAME)

        # ---- full staging (current tree, minus derived root sums) ----
        full = os.path.join(work, "full", FULL_NAME)
        os.makedirs(full, exist_ok=True)
        for rel in list_files(ROOT):
            if rel == FULL_SUMS_NAME:
                continue
            src = os.path.join(ROOT, rel.replace("/", os.sep))
            dst = os.path.join(full, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

        # ---- audits ----
        v = verify_red_line_headers(full, base_ref)
        if v:
            _fail("red-line header audit", v)
        print("red-line header audit: OK (6 headers byte-identical to canonical-full)")

        v = verify_protected_unchanged(full, base_ref)
        if v:
            _fail("protected-dir audit", v)
        print("protected-dir audit: OK (model/weights/labels/preprocess/contracts "
              "byte-identical)")

        v = verify_canonical_components(full, base_ref)
        if v:
            _fail("canonical-component audit", v)
        print("canonical-component audit: OK (3 CI16 + headers byte-identical to base)")

        v = audit_dependency_closure(full, files=PATCH_FILES)
        if v:
            _fail("dependency-closure audit", v)
        print("dependency-closure audit: OK")

        v = audit_complete_delta(full, base_ref, PATCH_FILES)
        if v:
            _fail("complete-delta audit", v)
        print("complete-delta audit: OK (patch + canonical-full base == full tree)")

        for rel in list_files(full):
            if "external_rf" in rel or "pluto_external" in rel:
                _fail("old-fix10 zero-residual", [rel + " leaked"])
        print("old-fix10 zero-residual: OK")

        # ---- patch staging (flat) ----
        p = os.path.join(work, "patch")
        for rel in PATCH_FILES:
            src = os.path.join(ROOT, rel.replace("/", os.sep))
            write_bytes(os.path.join(p, rel.replace("/", os.sep)),
                        open(src, "rb").read())

        v = audit_dependency_closure(p, files=PATCH_FILES, extra_roots=(base_ref,))
        if v:
            _fail("patch self-containment audit", v)
        print("patch self-containment audit: OK (patch overlays onto canonical-full alone)")

        v = verify_patch_overlay(base_ref, p, full)
        if v:
            _fail("patch-over-base overlay audit", v)
        print("patch-over-base overlay audit: OK (literal byte-level == full)")

        # ---- sums + tarballs ----
        p_n = write_sums(p, PATCH_SUMS_NAME)
        full_n = write_sums(full, FULL_SUMS_NAME)

        os.makedirs(DIST, exist_ok=True)
        patch_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        full_tar = os.path.join(DIST, FULL_TAR_BASENAME + ".tar.gz")
        build_tar_deterministic(make_tar_flat, p, patch_tar)
        build_tar_deterministic(make_tar, full, full_tar)
        print("determinism: OK (each tarball built twice, byte-identical)")

        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME),
                     os.path.join(DIST, PATCH_NAME + "_SHA256SUMS.txt"))
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_TAR_BASENAME + "_SHA256SUMS.txt"))

        # ---- self-check (independent unpack + sha256sum -c) ----
        print("== self-check ==")
        ok, total, good = verify_tar_flat(patch_tar, PATCH_SUMS_NAME)
        print("  %-26s files=%d ok=%d %s" % ("smoke-closeout patch", total, good,
                                              "PASS" if ok else "FAIL"))
        if not ok:
            sys.exit(1)
        ok, total, good = verify_tar(full_tar, FULL_SUMS_NAME, FULL_NAME)
        print("  %-26s files=%d ok=%d %s" % ("smoke-closeout full", total, good,
                                              "PASS" if ok else "FAIL"))
        if not ok:
            sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("smoke-closeout patch", patch_tar, p_n),
            ("smoke-closeout full", full_tar, full_n),
        ]:
            print("  %-26s %d content-files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
