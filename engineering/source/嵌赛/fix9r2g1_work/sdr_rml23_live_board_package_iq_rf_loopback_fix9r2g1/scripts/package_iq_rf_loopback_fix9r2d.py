#!/usr/bin/env python3
"""Package RML23 Route F fix9r2d -- diagnostic capture ENHANCEMENT (observability
completion, approved 39e5), layered on top of fix9r2b full.

fix9r2b (sdr_rml23_live_board_package_iq_rf_loopback_fix9r2b.tar.gz, sha
27ceb83322ae385bc74a0625b2088cc3cac769fb0f27172655798b1130755b42) was DELIVERED and
READY-FOR-BOARD-TEST.  Its R8 2-sample diagnostic run landed 5 waveforms; the fix9r2c
offline analyzer corrected three complex-math bugs and ruled the residual
NOT_PROVEN (root cause not identified).  fix9r2d is the ONE approved follow-up:
capture the raw RX slices + capture metadata + per-slice provenance so the offline
analyzer can name the residual with exactly one of six verdicts.

CRITICAL (requirement 1): this package is built on the fix9r2b full baseline and MUST
carry the full fix9r2c Phase 1 change set as well, so the fix9r2d package never re-
introduces the old complex-math bug:

  fix9r2c Phase 1 (already on disk, never separately packaged):
    MODIFIED scripts/analyze_fix9r2b_residuals.py            (3 complex-math bug fixes)
    NEW      scripts/test_fix9r2c_analyzer_regression.py     (16/16 analyzer regression)
    NEW      docs/..._FIX9R2C_OBSERVABILITY_AUDIT.md         (replay feasibility (a)/(b))

  fix9r2d diagnostic capture (this change set):
    NEW      board_package/iq_rf_fix9r2d_diagnostic.hpp      (8-slice provenance capture)
    NEW      host_tests/test_iq_rf_fix9r2d.cpp               (74-assertion host test)
    NEW      scripts/analyze_fix9r2d_capture.py              (6-verdict offline analyzer)
    NEW      scripts/package_iq_rf_loopback_fix9r2d.py       (this packager)
    NEW      docs/..._FIX9R2D_AUDIT.md                       (audit + acceptance record)
    MODIFIED board_package/iq_rf_loopback_23class_fix9r.hpp  (8 waveform + capture meta)
    MODIFIED host_tests/build_host_tests.sh                  (build fix9r2d test; strip fix10)
    MODIFIED host_tests/run_tests.sh                         (run fix9r2d test; strip fix10)

The fix9r2d capture saves EIGHT waveforms per R8 file (raw_aligned_rx_training/payload/
full_frame + raw_cycle_0/1_full_frame + expected_training/payload +
provisional_recovered_payload) with a per-slice provenance proof (mem_slice_sha256 ==
file sha256 -> equality==1), plus a per-capture metadata manifest (capture SHA / frame
indices / RMS / DC / peak / clip / CFO / SRO / gain / complete).  NO change to the
recovery algorithm, sync search, frame layout, TX data, model/label/preprocess, or any
threshold.  No fix10 recovery.  DIAGNOSTIC-ONLY.

IMPORTANT (fix10 pause): Route G fix10 is PAUSED and its on-disk files are preserved.
Two wiring files (host_tests/build_host_tests.sh and host_tests/run_tests.sh) carry
BOTH fix9r2b, fix9r2d AND fix10 edits on disk.  This packager reconstructs those two to
their FIX9R2D-ONLY content by removing the fix10 edits (the fix10 on-disk files are never
touched), so the produced package is exactly fix9r2b + fix9r2c Phase 1 + fix9r2d.

Produces, under dist/ (leaving every earlier package untouched, INCLUDING the fix9r2b
package it builds on):

  1. sdr_rml23_live_iq_rf_loopback_fix9r2d_patch.tar.gz          (fix9r2c Phase 1 + fix9r2d)
  2. sdr_rml23_live_board_package_iq_rf_loopback_fix9r2d.tar.gz  (fix9r2b full + the change set)

Each tarball is self-contained: a top directory holding the changed files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten.
Packaging permissions: directories 0755 / *.sh 0755 / everything else 0644.

A dependency-closure audit walks the transitive #include closure of every fix9r2d
C/C++ file AGAINST the clean full tree (fix9r2b baseline + change-set files) and
ABORTS if any resolved header differs from the fix9r2b baseline but is not in
ROUTE_F_FIX9R2D_FILES.

stdlib only.  Run with:  python3 scripts/package_iq_rf_loopback_fix9r2d.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_iq_rf_loopback_fix9r2b.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_iq_rf_loopback_fix9r2b"
BASE_SHA = "27ceb83322ae385bc74a0625b2088cc3cac769fb0f27172655798b1130755b42"

PATCH_NAME = "sdr_rml23_live_iq_rf_loopback_fix9r2d_patch"
PATCH_SUMS_NAME = "IQ_RF_LOOPBACK_FIX9R2D_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_rf_loopback_fix9r2d"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# NEW files (copied verbatim from the working tree): fix9r2c Phase 1 + fix9r2d.
ROUTE_F_FIX9R2D_NEW_FILES = [
    "board_package/iq_rf_fix9r2d_diagnostic.hpp",             # NEW (fix9r2d provenance capture)
    "host_tests/test_iq_rf_fix9r2d.cpp",                      # NEW (fix9r2d host test)
    "scripts/analyze_fix9r2d_capture.py",                     # NEW (fix9r2d offline analyzer)
    "scripts/package_iq_rf_loopback_fix9r2d.py",              # NEW (this packager)
    "scripts/test_fix9r2c_analyzer_regression.py",            # NEW (fix9r2c Phase 1 regression)
    "docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX9R2C_OBSERVABILITY_AUDIT.md",  # NEW (fix9r2c)
    "docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX9R2D_AUDIT.md",                # NEW (fix9r2d)
]

# MODIFIED files: fix9r2c Phase 1 + fix9r2d.  The two shell scripts carry fix10 edits
# on disk and are reconstructed to fix9r2d-only content by _FIX10_REMOVAL; the runner
# and the fix9r2c analyzer are copied verbatim (they carry no fix10 edits).
ROUTE_F_FIX9R2D_MODIFIED_FILES = [
    "scripts/analyze_fix9r2b_residuals.py",                   # MODIFIED (fix9r2c complex-math fix)
    "board_package/iq_rf_loopback_23class_fix9r.hpp",         # MODIFIED (fix9r2d 8 waveform + capture meta)
    "host_tests/build_host_tests.sh",                         # MODIFIED (build fix9r2d test; strip fix10)
    "host_tests/run_tests.sh",                                # MODIFIED (run fix9r2d test; strip fix10)
]

ROUTE_F_FIX9R2D_FILES = ROUTE_F_FIX9R2D_NEW_FILES + ROUTE_F_FIX9R2D_MODIFIED_FILES


# ---------------------------------------------------------------------------
# fix10 removal: each transform returns the fix9r2d-only text of one on-disk file.
# (The two shared wiring files carry fix9r2b + fix9r2d + fix10 on disk; strip fix10.)
# ---------------------------------------------------------------------------
def _strip_fix10_build(text):
    old = ('echo "== build test_iq_external_rf_rx_23class =="\n'
           '$CXX $FLAGS test_iq_external_rf_rx_23class.cpp -o bin/test_iq_external_rf_rx_23class\n'
           '\n'
           'echo "== build test_pluto_external_tx =="\n'
           '$CXX $FLAGS test_pluto_external_tx.cpp -o bin/test_pluto_external_tx\n'
           '\n')
    assert text.count(old) == 1, "build_host_tests.sh fix10 entries not unique/found"
    text = text.replace(old, "")

    old = 'test_iq_rf_fix9r2d,test_iq_external_rf_rx_23class,test_pluto_external_tx}'
    assert text.count(old) == 1, "build_host_tests.sh fix10 OK echo not unique/found"
    text = text.replace(old, 'test_iq_rf_fix9r2d}')

    assert "iq_external_rf_rx" not in text and "pluto_external_tx" not in text
    assert "test_iq_rf_fix9r2b" in text and "test_iq_rf_fix9r2d" in text
    return text


def _strip_fix10_run(text):
    old = ('./bin/test_iq_rf_fix9r2d || rc=1\n'
           './bin/test_iq_external_rf_rx_23class || rc=1\n'
           './bin/test_pluto_external_tx || rc=1\n')
    assert text.count(old) == 1, "run_tests.sh fix10 entries not unique/found"
    text = text.replace(old, './bin/test_iq_rf_fix9r2d || rc=1\n')
    assert "iq_external_rf_rx" not in text and "pluto_external_tx" not in text
    assert "test_iq_rf_fix9r2b" in text and "test_iq_rf_fix9r2d" in text
    return text


_FIX10_REMOVAL = {
    "host_tests/build_host_tests.sh": _strip_fix10_build,
    "host_tests/run_tests.sh": _strip_fix10_run,
}


def _fix9r2d_content(rel):
    """Return the fix9r2d-only content of a file (fix10 stripped for MODIFIED files)."""
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8", newline="\n") as f:
        text = f.read()
    if rel in _FIX10_REMOVAL:
        return _FIX10_REMOVAL[rel](text)
    return text


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
    """Deterministic tar.gz with EXPLICIT member modes (dir/.sh -> 0755, else 0644)."""
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


def _cpp_includes(text):
    out = []
    for line in text.splitlines():
        m = _INCLUDE_RE.match(line)
        if m:
            out.append(m.group(1))
    return out


def _rel_of(base, path):
    return os.path.relpath(os.path.abspath(path), base).replace(os.sep, "/")


def audit_dependency_closure(full_dir, base_dir):
    """Fail-closed closure audit over the CLEAN full tree (fix9r2b baseline + change set)."""
    base_sha = {}
    for dirpath, dirnames, filenames in os.walk(base_dir):
        dirnames.sort()
        for name in filenames:
            full = os.path.join(dirpath, name)
            base_sha[_rel_of(base_dir, full)] = sha256_of(full)

    fix9r2d_set = set(ROUTE_F_FIX9R2D_FILES)
    violations = set()
    seen = set()
    queue = [rel for rel in ROUTE_F_FIX9R2D_FILES if rel.endswith(_CPP_EXT)]

    while queue:
        rel = queue.pop()
        abs_path = os.path.join(full_dir, rel.replace("/", os.sep))
        if abs_path in seen:
            continue
        seen.add(abs_path)
        if not os.path.exists(abs_path):
            continue
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            includes = _cpp_includes(f.read())
        for inc in includes:
            resolved = os.path.normpath(os.path.join(os.path.dirname(abs_path), inc))
            rrel = _rel_of(full_dir, resolved)
            if not os.path.exists(resolved):
                continue  # board-toolchain/system header not present in the tree
            if rrel in base_sha:
                if sha256_of(resolved) != base_sha[rrel] and rrel not in fix9r2d_set:
                    violations.add(rrel)
            else:
                if rrel not in fix9r2d_set:
                    violations.add(rrel)
            if resolved not in seen:
                queue.append(rrel)

    return sorted(violations)


def verify_content_consistency(base, full):
    """Prove fix9r2d content == fix9r2b content except the change-set files + SUMS."""
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

    new_set = set(ROUTE_F_FIX9R2D_NEW_FILES)
    mod_set = set(ROUTE_F_FIX9R2D_MODIFIED_FILES)
    changed_paths = set(rel for rel, _ in changed)
    extra = sorted(set(full_map) - set(base_map))
    expected_extra = new_set - {"SHA256SUMS.txt"}
    return unchanged, changed, extra, changed_paths, mod_set, expected_extra


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    actual = sha256_of(BASE_TAR)
    if actual != BASE_SHA:
        sys.exit("baseline package SHA mismatch:\n  expected %s\n  got      %s" % (BASE_SHA, actual))

    for rel in ROUTE_F_FIX9R2D_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    content = {}
    for rel in ROUTE_F_FIX9R2D_FILES:
        content[rel] = _fix9r2d_content(rel)

    work = tempfile.mkdtemp(prefix="pkg_rfloop_fix9r2d_")
    try:
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in ROUTE_F_FIX9R2D_FILES:
            write_bytes(os.path.join(full, rel.replace("/", os.sep)),
                        content[rel].encode("utf-8"))

        # ---- content-consistency proof ----
        unchanged, changed, extra, changed_paths, mod_set, expected_extra = \
            verify_content_consistency(base, full)
        if sorted(changed_paths) != sorted(mod_set):
            print("content-consistency FAILED: changed files != MODIFIED set:", file=sys.stderr)
            print("  changed files:", sorted(changed_paths), file=sys.stderr)
            print("  MODIFIED set:  ", sorted(mod_set), file=sys.stderr)
            sys.exit(1)
        if sorted(extra) != sorted(expected_extra):
            print("content-consistency FAILED: extra files != NEW set:", file=sys.stderr)
            print("  extra files:", sorted(extra), file=sys.stderr)
            print("  NEW set:    ", sorted(expected_extra), file=sys.stderr)
            sys.exit(1)
        print("content-consistency: OK (%d fix9r2b files byte-identical, "
              "%d modified, +%d new)" % (len(unchanged), len(changed_paths), len(extra)))

        # ---- dependency-closure audit (fail-closed) ----
        violations = audit_dependency_closure(full, base)
        if violations:
            print("dependency-closure audit FAILED: headers differ from the fix9r2b "
                  "baseline (or are absent from it) but are NOT listed in "
                  "ROUTE_F_FIX9R2D_FILES:", file=sys.stderr)
            for v in violations:
                print("  " + v, file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK (all changed headers covered by ROUTE_F_FIX9R2D_FILES)")

        # ---- 1. fix9r2d patch (fix9r2c Phase 1 + fix9r2d) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_F_FIX9R2D_FILES:
            write_bytes(os.path.join(p, rel.replace("/", os.sep)),
                        content[rel].encode("utf-8"))
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: fix9r2b baseline + fix9r2c Phase 1 + fix9r2d ----
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix9r2d patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (fix9r2b + fix9r2c + fix9r2d)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-42s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix9r2d patch", p_tar, p_n),
            ("merged full (fix9r2b + fix9r2c + fix9r2d)", full_tar, full_n),
        ]:
            print("  %-42s %d content-files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
