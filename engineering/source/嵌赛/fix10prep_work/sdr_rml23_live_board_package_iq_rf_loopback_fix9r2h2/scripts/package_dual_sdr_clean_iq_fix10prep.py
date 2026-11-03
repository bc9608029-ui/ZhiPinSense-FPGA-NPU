#!/usr/bin/env python3
"""Package the fix10-prep three-path delivery (N9).

fix10-prep adds THREE independent auditable paths on top of the Route F fix9r2h2
baseline (which is itself the authoritative fix9r2g1 full + the fix9r2h / h1 / h2
Route F refinements -- narrower payload training, shared residual gate, tx-scale
contract), WITHOUT touching the model / weights / labels / 24->23 mapping / gates:

  Path A  RadioML CI16  -> TX SDR -> coax/RF -> RX SDR -> shared recovery -> model
          (board_package/iq_dual_sdr_23class_fix10.hpp + _transfer_fix10.hpp +
           _coarse_cfo_recovery.hpp + sdr_adapter/pluto_dual_air_link.hpp)
  Path B  generated-clean CI16 -> existing PreprocessChain -> D2 restore -> model
          (board_package/iq_clean_iq_23class_fix10.hpp + iq_clean_baseline.hpp +
           scripts/gen_generated_clean_23.py + scripts/predict_clean_baseline.py)
  Path C  generated-clean CI16 -> TX SDR -> coax/RF -> RX SDR -> same model
          (reuses Path B artifacts, Path A transfer machinery)

The change set is EXACTLY the fix10-prep delta (verified against the fix9r2g1
manifest e3db0872...): the three fix9r2h* audit docs and the seven Route F headers
that differ from fix9r2g1 are the fix9r2h2 BASELINE (already present in the full
package), NOT part of the fix10-prep patch.

Produces, under dist/ (leaving any earlier package untouched):
  1. sdr_rml23_live_iq_rf_loopback_fix10prep_patch.tar.gz   (fix10-prep change set)
  2. sdr_rml23_live_board_package_iq_rf_loopback_fix10prep.tar.gz  (full tree)

Each tarball carries a SHA256SUMS in the repo's `HASH *relpath` convention
(sha256sum -b).  stdlib only; deterministic (uid/gid 0, mtime 0, sorted entries,
gzip level 9, mtime 0).

Run with:  python scripts/package_dual_sdr_clean_iq_fix10prep.py
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

PATCH_NAME = "sdr_rml23_live_iq_rf_loopback_fix10prep_patch"
PATCH_SUMS_NAME = "FIX10PREP_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_rf_loopback_fix10prep"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# Directories never packaged (build products / python cache / output).
EXCLUDED_DIRS = {"host_tests/bin", "scripts/__pycache__", "dist", ".git"}

# ---- the fix10-prep change set (the ONLY thing the patch carries) ----
# NEW files (three paths + packager + audit).
FIX10PREP_NEW_FILES = [
    "sdr_adapter/pluto_dual_air_link.hpp",             # N1 dual-device Fake link
    "board_package/iq_dual_sdr_transfer_fix10.hpp",    # N2 dual-SDR transfer
    "board_package/iq_dual_sdr_coarse_cfo_recovery.hpp",  # coarse-CFO fix
    "board_package/iq_dual_sdr_23class_fix10.hpp",     # N3 dual-SDR 23-class runner
    "board_package/iq_clean_baseline.hpp",             # N4a clean baseline loader
    "board_package/iq_clean_iq_23class_fix10.hpp",     # N4  clean digital runner
    "scripts/gen_generated_clean_23.py",               # N5 clean CI16 generator
    "scripts/predict_clean_baseline.py",               # N6 frozen offline baseline
    "host_tests/test_iq_dual_sdr_fix10.cpp",           # N7 dual-SDR 36 cases
    "host_tests/test_iq_dual_sdr_23class_fix10.cpp",   # Stage 2 dual-SDR runner test
    "host_tests/test_clean_iq_23class_fix10.cpp",      # N8 clean E2E
    "scripts/package_dual_sdr_clean_iq_fix10prep.py",  # N9 this packager
    "docs/M29_RML23_FIX10_DUAL_SDR_CLEAN_IQ_PREP_AUDIT.md",  # N10 audit
]

# MODIFIED wiring (phase dispatch + host build/run) -- the ONLY existing files
# the fix10-prep paths touch.  Nothing here is model/weights/labels/preprocess.
FIX10PREP_MODIFIED_FILES = [
    "board_package/gate9_phase.hpp",
    "board_package/board_gate9_full_chain_rml23.cpp",
    "host_tests/build_host_tests.sh",
    "host_tests/run_tests.sh",
]

FIX10PREP_FILES = FIX10PREP_NEW_FILES + FIX10PREP_MODIFIED_FILES
FIX10PREP_NEW_SET = set(FIX10PREP_NEW_FILES)
FIX10PREP_MOD_SET = set(FIX10PREP_MODIFIED_FILES)

# Directories whose contents must be byte-identical to the Route F baseline
# (the fix10-prep guarantee: no model/weights/labels/preprocess/mapping/gate edits).
PROTECTED_DIRS = ("model_rml23/", "model_12class/", "contracts/",
                  "deployment_golden/")

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
    """Rel-paths of packaged files (excludes build products / pycache / output)."""
    out = []
    for dirpath, dirnames, filenames in os.walk(stage):
        dirnames[:] = sorted(
            d for d in dirnames
            if os.path.relpath(os.path.join(dirpath, d), stage).replace(os.sep, "/")
            not in EXCLUDED_DIRS)
        for name in filenames:
            out.append(os.path.relpath(os.path.join(dirpath, name), stage)
                       .replace(os.sep, "/"))
    return sorted(out)


def write_sums(stage, sums_name):
    rels = [r for r in list_files(stage) if r != sums_name]
    lines = ["%s *%s\n" % (sha256_of(os.path.join(stage, rel.replace("/", os.sep))), rel)
             for rel in rels]
    write_bytes(os.path.join(stage, sums_name), "".join(sorted(lines)).encode("utf-8"))
    return len(rels)


def make_tar(stage, tar_path):
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
            entries.append((os.path.relpath(os.path.join(dirpath, name), stage)
                            .replace(os.sep, "/"), False))
    entries.sort(key=lambda e: e[0])

    with tarfile.open(raw, "w", format=tarfile.GNU_FORMAT) as t:
        for rel, is_dir in entries:
            full = stage if rel == "" else os.path.join(stage, rel.replace("/", os.sep))
            arc = top if rel == "" else os.path.join(top, rel).replace(os.sep, "/")
            info = t.gettarinfo(full, arcname=arc)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            info.mode = 0o755 if is_dir else (0o755 if rel.endswith(".sh") else 0o644)
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
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(tar_path, "r:gz") as t:
            t.extractall(td)
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


def _cpp_includes(text):
    out = []
    for line in text.splitlines():
        m = _INCLUDE_RE.match(line)
        if m:
            out.append(m.group(1))
    return out


# Include-search dirs that mirror host_tests/build_host_tests.sh:
#   -I../board_package -I../sdr_adapter -I../ui_sw
# (relative to the tree root).  Quoted includes also search the including file's
# own directory first (standard C++ rule).
_INCLUDE_DIRS = ("board_package", "sdr_adapter", "ui_sw")


def audit_dependency_closure(full_dir):
    """Fail-closed: every quoted include of every fix10-prep C++ file must resolve
    to a real file inside the full tree (system headers are angle-bracket, so they
    are not picked up here).  Resolution mirrors the host build: including-file
    dir, then -I dirs (board_package/sdr_adapter/ui_sw), then a unique basename
    anywhere in the tree.  A missing include means the patch is incomplete."""
    # basename index over the full tree (for the last-resort unique match).
    by_base = {}
    for dirpath, dirnames, filenames in os.walk(full_dir):
        dirnames[:] = sorted(
            d for d in dirnames
            if os.path.relpath(os.path.join(dirpath, d), full_dir).replace(os.sep, "/")
            not in EXCLUDED_DIRS)
        for name in filenames:
            if name.endswith(_CPP_EXT):
                p = os.path.join(dirpath, name)
                by_base.setdefault(name, []).append(p)

    missing = set()
    for rel in FIX10PREP_FILES:
        if not rel.endswith(_CPP_EXT):
            continue
        abs_path = os.path.join(full_dir, rel.replace("/", os.sep))
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            includes = _cpp_includes(f.read())
        for inc in includes:
            cands = [os.path.normpath(os.path.join(os.path.dirname(abs_path), inc))]
            cands += [os.path.normpath(os.path.join(full_dir, d, inc))
                      for d in _INCLUDE_DIRS]
            if not any(os.path.exists(c) for c in cands):
                # last resort: unique basename anywhere in the tree
                base = os.path.basename(inc)
                hits = by_base.get(base, [])
                if len(hits) != 1:
                    missing.add(rel + " -> " + inc)
    return sorted(missing)


def verify_protected_unchanged(full_dir, base_dir):
    """The fix10-prep guarantee: PROTECTED_DIRS are byte-identical to the Route F
    baseline tree (model/weights/labels/preprocess/mapping/gates untouched)."""
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


def main():
    # N9/N10 must exist before packaging (the audit is part of the patch).
    for rel in FIX10PREP_FILES:
        if not os.path.exists(os.path.join(ROOT, rel.replace("/", os.sep))):
            sys.exit("missing fix10-prep file: %s" % rel)

    # The protected-dir baseline reference (model/weights/labels/preprocess) is the
    # on-disk Route F tree it was branched from.
    base_ref = os.path.abspath(os.path.join(
        ROOT, os.pardir, os.pardir, "fix9r2g1_work",
        "sdr_rml23_live_board_package_iq_rf_loopback_fix9r2g1"))

    work = tempfile.mkdtemp(prefix="pkg_fix10prep_")
    try:
        # ---- stage the full tree (the complete fix9r2h2 + fix10-prep state) ----
        full = os.path.join(work, FULL_NAME)
        os.makedirs(full, exist_ok=True)
        for rel in list_files(ROOT):
            if rel == FULL_SUMS_NAME:
                continue
            src = os.path.join(ROOT, rel.replace("/", os.sep))
            dst = os.path.join(full, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

        # ---- protected-dir proof (model/weights/labels/preprocess unchanged) ----
        protected_viol = verify_protected_unchanged(full, base_ref)
        if protected_viol:
            print("protected-dir audit FAILED (model/weights/labels/preprocess "
                  "touched):", file=sys.stderr)
            for v in protected_viol:
                print("  " + v, file=sys.stderr)
            sys.exit(1)
        print("protected-dir audit: OK (model/weights/labels/preprocess/mapping "
              "byte-identical to baseline)")

        # ---- dependency-closure audit (patch C++ includes all resolve) ----
        missing = audit_dependency_closure(full)
        if missing:
            print("dependency-closure audit FAILED:", file=sys.stderr)
            for v in missing:
                print("  " + v, file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK")

        # ---- fix9r1 / old-fix10 zero-residual ----
        for rel in list_files(full):
            if "external_rf" in rel or "pluto_external" in rel:
                print("old-fix10 zero-residual FAILED: %s leaked" % rel,
                      file=sys.stderr)
                sys.exit(1)
        print("old-fix10 zero-residual: OK")

        # ---- 1. patch (the fix10-prep change set) ----
        p = os.path.join(work, PATCH_NAME)
        for rel in FIX10PREP_FILES:
            src = os.path.join(ROOT, rel.replace("/", os.sep))
            write_bytes(os.path.join(p, rel.replace("/", os.sep)),
                        open(src, "rb").read())
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        os.makedirs(DIST, exist_ok=True)
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME),
                     os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. full (complete fix9r2h2 + fix10-prep tree) ----
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check (independent unpack + sha256sum -c) ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix10-prep patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("fix10-prep full", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-24s files=%d ok=%d %s" % (label, total, good,
                                                 "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix10-prep patch", p_tar, p_n),
            ("fix10-prep full", full_tar, full_n),
        ]:
            print("  %-24s %d content-files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
