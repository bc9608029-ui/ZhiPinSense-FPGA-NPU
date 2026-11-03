#!/usr/bin/env python3
"""Package RML23 Route F fix9r2g1 -- the minimal hotfix that repairs the baseline
PRODUCTION/CONSUMPTION contract, layered on top of the fix9r2g full package.

Root cause (fix9r2g defect): the fix9r2g package shipped a 5-column baseline generator
(scripts/build_route_f_fix9r_exact_baseline.py, no `frozen_baseline_pred`, no
`--predictions`) while the C++ loader (iq_rf_fix9r_baseline.hpp) requires 6 columns and
fails closed on a short row, so R8 would necessarily fail BEFORE any RF.  fix9r2g1
delivers the 6-column generator plus a REAL frozen-model prediction TSV (46 holdout
predictions produced by deterministic inference, never `deployed_class`), plus an
end-to-end test that runs the formal Python generator and reads the result back with the
formal C++ loader.

THIS FIX CHANGES NO RF ALGORITHM, training block, model, threshold, or R8 condition.

CRITICAL: this package is built on the fix9r2g FULL baseline
(sdr_rml23_live_board_package_iq_rf_loopback_fix9r2g.tar.gz, sha
feb30403e08924e83945ec23d75a2d6bb46213bba9bb15a7ef96ebd2c55e808e), so it carries the
entire fix9r2c Phase 1 + fix9r2d + fix9r2g change set as well.

fix9r2g1 change set (this package):
  MODIFIED scripts/build_route_f_fix9r_exact_baseline.py   (5-col -> 6-col + predictions)
  NEW      scripts/predict_fix9r_frozen_baseline.py        (deterministic inference tool)
  NEW      scripts/route_f_fix9r_predictions.tsv           (46-row frozen-model predictions)
  NEW      host_tests/test_iq_rf_loopback_fix9r2g1_baseline_e2e.cpp (generator->loader E2E)
  MODIFIED host_tests/build_host_tests.sh                  (build the E2E test)
  MODIFIED host_tests/run_tests.sh                         (run the E2E test)
  NEW      docs/M29_RML23_FIX9R2G1_BASELINE_CONTRACT_FIX_AUDIT.md
  NEW      scripts/package_iq_rf_loopback_fix9r2g1.py      (this packager)

The two wiring files are reconstructed as fix9r2g-content + the E2E test (the on-disk
copies also carry paused fix10 edits, which are never packaged; fix10 zero-residual).

Produces, under dist/ (leaving every earlier package untouched):
  1. sdr_rml23_live_iq_rf_loopback_fix9r2g1_patch.tar.gz         (fix9r2g1 change set)
  2. sdr_rml23_live_board_package_iq_rf_loopback_fix9r2g1.tar.gz (fix9r2g full + change set)

Each tarball carries a SHA256SUMS in the repo's `HASH *relpath` convention (sha256sum -b).
stdlib only.  Run with:  python3 scripts/package_iq_rf_loopback_fix9r2g1.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_iq_rf_loopback_fix9r2g.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_iq_rf_loopback_fix9r2g"
BASE_SHA = "feb30403e08924e83945ec23d75a2d6bb46213bba9bb15a7ef96ebd2c55e808e"

PATCH_NAME = "sdr_rml23_live_iq_rf_loopback_fix9r2g1_patch"
PATCH_SUMS_NAME = "IQ_RF_LOOPBACK_FIX9R2G1_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_rf_loopback_fix9r2g1"
FULL_SUMS_NAME = "SHA256SUMS.txt"

ROUTE_F_FIX9R2G1_NEW_FILES = [
    "scripts/predict_fix9r_frozen_baseline.py",                 # deterministic inference tool
    "scripts/route_f_fix9r_predictions.tsv",                    # 46-row frozen predictions
    "host_tests/test_iq_rf_loopback_fix9r2g1_baseline_e2e.cpp", # generator->loader E2E
    "docs/M29_RML23_FIX9R2G1_BASELINE_CONTRACT_FIX_AUDIT.md",   # audit + acceptance
    "scripts/package_iq_rf_loopback_fix9r2g1.py",               # this packager
]

ROUTE_F_FIX9R2G1_MODIFIED_FILES = [
    "scripts/build_route_f_fix9r_exact_baseline.py",            # 5-col -> 6-col
    "host_tests/build_host_tests.sh",                           # + E2E build (fix10 stripped)
    "host_tests/run_tests.sh",                                  # + E2E run  (fix10 stripped)
]

ROUTE_F_FIX9R2G1_FILES = ROUTE_F_FIX9R2G1_NEW_FILES + ROUTE_F_FIX9R2G1_MODIFIED_FILES


# ---------------------------------------------------------------------------
# E2E wiring injection: these transforms take the fix9r2g-FULL (fix10-free) text
# of the two shell scripts and add the E2E test build/run lines.
# ---------------------------------------------------------------------------
def inject_e2e_build(text):
    old_compile = ('$CXX $FLAGS test_iq_rf_loopback_23class_fix9r2g.cpp '
                   '../sdr_adapter/pluto_tx.cpp -o bin/test_iq_rf_loopback_23class_fix9r2g\n')
    assert text.count(old_compile) == 1, "build: fix9r2g compile line not unique/found"
    add = (old_compile +
           '\necho "== build test_iq_rf_loopback_fix9r2g1_baseline_e2e =="\n'
           '$CXX $FLAGS test_iq_rf_loopback_fix9r2g1_baseline_e2e.cpp '
           '-o bin/test_iq_rf_loopback_fix9r2g1_baseline_e2e\n')
    text = text.replace(old_compile, add)

    old_sum = 'test_iq_rf_loopback_23class_fix9r2g}'
    assert text.count(old_sum) == 1, "build: fix9r2g summary tail not unique/found"
    text = text.replace(old_sum, 'test_iq_rf_loopback_23class_fix9r2g,'
                                 'test_iq_rf_loopback_fix9r2g1_baseline_e2e}')
    assert "test_iq_rf_loopback_fix9r2g1_baseline_e2e" in text
    assert "iq_external_rf_rx" not in text and "pluto_external_tx" not in text
    return text


def inject_e2e_run(text):
    old_run = './bin/test_iq_rf_loopback_23class_fix9r2g || rc=1\n'
    assert text.count(old_run) == 1, "run: fix9r2g run line not unique/found"
    text = text.replace(old_run, old_run + './bin/test_iq_rf_loopback_fix9r2g1_baseline_e2e || rc=1\n')
    assert "test_iq_rf_loopback_fix9r2g1_baseline_e2e" in text
    assert "iq_external_rf_rx" not in text and "pluto_external_tx" not in text
    return text


_E2E_INJECT = {
    "host_tests/build_host_tests.sh": inject_e2e_build,
    "host_tests/run_tests.sh": inject_e2e_run,
}


def _fix9r2g1_content(rel, base_dir):
    """Return the fix9r2g1 content of a file.

    For the two wiring scripts, the content is the fix9r2g-full (already fix10-free)
    text read from `base_dir` with the E2E test injected.  Every other file is copied
    verbatim from the working tree.
    """
    if rel in _E2E_INJECT:
        with open(os.path.join(base_dir, rel.replace("/", os.sep)), "r",
                  encoding="utf-8", newline="\n") as f:
            return _E2E_INJECT[rel](f.read())
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8", newline="\n") as f:
        return f.read()


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
            out.append(os.path.relpath(os.path.join(dirpath, name), stage).replace(os.sep, "/"))
    return sorted(out)


def write_sums(stage, sums_name):
    rels = [r for r in list_files(stage) if r != sums_name]
    lines = []
    for rel in rels:
        lines.append("%s *%s\n" % (sha256_of(os.path.join(stage, rel.replace("/", os.sep))), rel))
    write_bytes(os.path.join(stage, sums_name), "".join(sorted(lines)).encode("utf-8"))
    return len(rels)


def make_tar(stage, tar_path):
    top = os.path.basename(stage.rstrip("/\\"))
    raw = tar_path + ".tmp.tar"

    entries = [("", True)]
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
    """Fail-closed closure audit: every header the E2E test includes must resolve to
    either the fix9r2g baseline or a file listed in the fix9r2g1 change set."""
    base_sha = {}
    for dirpath, dirnames, filenames in os.walk(base_dir):
        dirnames.sort()
        for name in filenames:
            full = os.path.join(dirpath, name)
            base_sha[_rel_of(base_dir, full)] = sha256_of(full)

    fix9r2g1_set = set(ROUTE_F_FIX9R2G1_FILES)
    violations = set()
    seen = set()
    queue = [rel for rel in ROUTE_F_FIX9R2G1_FILES if rel.endswith(_CPP_EXT)]

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
                continue
            if rrel in base_sha:
                if sha256_of(resolved) != base_sha[rrel] and rrel not in fix9r2g1_set:
                    violations.add(rrel)
            elif rrel not in fix9r2g1_set:
                violations.add(rrel)
            if resolved not in seen:
                queue.append(rrel)

    return sorted(violations)


def verify_content_consistency(base, full):
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

    changed = []
    unchanged = []
    for rel in sorted(base_map):
        if rel == "SHA256SUMS.txt":
            continue
        if rel not in full_map:
            changed.append((rel, "MISSING"))
        elif full_map[rel] != base_map[rel]:
            changed.append((rel, "DIFFER"))
        else:
            unchanged.append(rel)

    new_set = set(ROUTE_F_FIX9R2G1_NEW_FILES)
    mod_set = set(ROUTE_F_FIX9R2G1_MODIFIED_FILES)
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

    for rel in ROUTE_F_FIX9R2G1_FILES:
        if rel not in _E2E_INJECT and not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    work = tempfile.mkdtemp(prefix="pkg_rfloop_fix9r2g1_")
    try:
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))

        for rel in ROUTE_F_FIX9R2G1_FILES:
            write_bytes(os.path.join(full, rel.replace("/", os.sep)),
                        _fix9r2g1_content(rel, base).encode("utf-8"))

        # ---- content-consistency proof ----
        unchanged, changed, extra, changed_paths, mod_set, expected_extra = \
            verify_content_consistency(base, full)
        if sorted(changed_paths) != sorted(mod_set):
            print("content-consistency FAILED: changed != MODIFIED", file=sys.stderr)
            print("  changed:  %s" % sorted(changed_paths), file=sys.stderr)
            print("  MODIFIED: %s" % sorted(mod_set), file=sys.stderr)
            sys.exit(1)
        if sorted(extra) != sorted(expected_extra):
            print("content-consistency FAILED: extra != NEW", file=sys.stderr)
            print("  extra: %s" % extra, file=sys.stderr)
            print("  NEW:   %s" % expected_extra, file=sys.stderr)
            sys.exit(1)
        print("content-consistency: OK (%d fix9r2g files byte-identical, %d modified, +%d new)"
              % (len(unchanged), len(changed_paths), len(extra)))

        # ---- dependency-closure audit ----
        violations = audit_dependency_closure(full, base)
        if violations:
            print("dependency-closure audit FAILED:", file=sys.stderr)
            for v in violations:
                print("  " + v, file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK")

        # ---- fix10 zero-residual ----
        for dirpath, dirnames, filenames in os.walk(full):
            for name in filenames:
                if "external_rf" in name or "pluto_external" in name:
                    print("fix10 zero-residual FAILED: %s leaked"
                          % os.path.relpath(os.path.join(dirpath, name), full), file=sys.stderr)
                    sys.exit(1)
        print("fix10 zero-residual: OK")

        # ---- 1. patch (change set) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_F_FIX9R2G1_FILES:
            write_bytes(os.path.join(p, rel.replace("/", os.sep)),
                        _fix9r2g1_content(rel, base).encode("utf-8"))
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full (fix9r2g + fix9r2g1) ----
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix9r2g1 patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (fix9r2g + fix9r2g1)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-42s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix9r2g1 patch", p_tar, p_n),
            ("merged full (fix9r2g + fix9r2g1)", full_tar, full_n),
        ]:
            print("  %-42s %d content-files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
