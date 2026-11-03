#!/usr/bin/env python3
"""Package the RML23 Stage H-E / Route E (same-device modulated-IQ digital
loopback) as an independent patch plus the merged full board package.

Route E is the Stage H-E coding increment on top of the already-shipped Stage G
route D (sdr_rml23_live_board_package_synthetic_iq_route_d.tar.gz, sha 5a4c4d3a…).
It adds:
  * the pure-logic loopback header + the board-only runner header (new),
  * the Route C --raw-iq-out-dir persistence (generated-2p56m int16 + manifest),
  * the --phase=iq-digital-loopback dispatch,
  * the host test + analyzer + verdict template,
  * the RawRxOutput::{iq,pushed_complex,quant_scale} field-access guard test.
It touches NOTHING outside Stage H-E: no model / labels / golden / RTL / bitstream
/ Flash; no Stage G A/B/C/D semantics; no digital/rf/ambient/live-rx semantics.

Produces, under dist/ (leaving every earlier package untouched, INCLUDING the
erroneous 2d8b8bab… package it replaces):

  1. sdr_rml23_live_iq_digital_loopback_fix1_patch.tar.gz         (Route E only)
  2. sdr_rml23_live_board_package_iq_digital_loopback_fix1.tar.gz (route D + E)

The fix1 suffix marks this as the packaging errata fix: the first merged package
(2d8b8bab…) silently carried the route-D baseline synthetic_iq_runner.hpp (missing
RawRxOutput::{iq,pushed_complex,quant_scale}) because that header was modified in
the working tree but omitted from ROUTE_E_FILES.  See
docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_FIX1_AUDIT.md.

Two defenses are now in place:
  1. synthetic_iq_runner.hpp is explicitly listed (carried with full working-tree
     content).
  2. A dependency-closure audit (audit_dependency_closure) walks the transitive
     #include closure of every Route E C/C++ file and ABORTS if any resolved header
     differs from the baseline package but is not in ROUTE_E_FILES.  This is exactly
     the failure mode that produced 2d8b8bab… and now cannot recur silently.

The Route E patch is relative to the route D merged package (5a4c4d3a…).
The merged full is that route D package + the Route E files.  Modified files are
carried with their FULL working-tree content (route D baseline + Route E), so the
patch is self-contained.

Each tarball is self-contained: a top directory holding the changed files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten.

stdlib only.  Run with:  python3 scripts/package_iq_digital_loopback.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_synthetic_iq_route_d.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_synthetic_iq_route_d"

PATCH_NAME = "sdr_rml23_live_iq_digital_loopback_fix1_patch"
PATCH_SUMS_NAME = "IQ_DIGITAL_LOOPBACK_FIX1_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_digital_loopback_fix1"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# Route E files, relative to the repo root.  New files carried in full; modified
# files as route-D baseline + Route E.
ROUTE_E_FILES = [
    "board_package/iq_digital_loopback.hpp",          # NEW
    "board_package/iq_digital_loopback_runner.hpp",   # NEW
    "board_package/board_gate9_full_chain_rml23.cpp",  # MODIFIED (C persist + E dispatch)
    "board_package/gate9_phase.hpp",                  # MODIFIED (+iq-digital-loopback)
    "board_package/synthetic_iq_runner.hpp",          # MODIFIED (RawRxOutput iq/pushed_complex/quant_scale)
    "host_tests/test_iq_digital_loopback.cpp",        # NEW
    "host_tests/test_route_e_raw_rx_output_fields.cpp",  # NEW (compile-time field guard)
    "host_tests/build_host_tests.sh",                 # MODIFIED (+target)
    "host_tests/run_tests.sh",                        # MODIFIED (+run)
    "scripts/analyze_iq_digital_loopback.py",         # NEW
    "scripts/package_iq_digital_loopback.py",         # NEW (fix1 names + dep-closure audit)
    "scripts/run_gate9_rml23.sh",                     # MODIFIED (usage)
    "docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_AUDIT.md",           # NEW (audit + record)
    "docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_FIX1_AUDIT.md",      # NEW (root-cause audit)
    "docs/M29_RML23_STAGE_H_E_IQ_DIGITAL_LOOPBACK_VERDICT_TEMPLATE.md",  # NEW
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
    """Prevent the 'modified header silently reverted to baseline' bug (2d8b8bab…).

    Walk the transitive #include closure of every Route E C/C++ file.  For each
    resolved header whose bytes DIFFER from the baseline package (or which does not
    exist in the baseline at all), require it to be in ROUTE_E_FILES -- otherwise
    the merged full package would carry the stale baseline copy (or drop the header
    entirely) and the board compile would fail.  Returns a sorted list of
    violations (repo-root-relative paths); empty means the closure is safe.
    """
    base_sha = {}
    for dirpath, dirnames, filenames in os.walk(base_dir):
        dirnames.sort()
        for name in filenames:
            full = os.path.join(dirpath, name)
            base_sha[_rel_of(base_dir, full)] = sha256_of(full)

    route_e_set = set(ROUTE_E_FILES)
    violations = set()
    seen = set()
    queue = [rel for rel in ROUTE_E_FILES if rel.endswith(_CPP_EXT)]

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
                if sha256_of(resolved) != base_sha[rrel] and rrel not in route_e_set:
                    violations.add(rrel)
            else:
                # header present in working tree but absent from baseline
                if rrel not in route_e_set:
                    violations.add(rrel)
            if resolved not in seen:
                queue.append(rrel)

    return sorted(violations)


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    for rel in ROUTE_E_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    work = tempfile.mkdtemp(prefix="pkg_iqdloop_")
    try:
        # ---- extract baseline once ----
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- dependency-closure audit (fail-closed, before any package is built) ----
        violations = audit_dependency_closure(base)
        if violations:
            print("dependency-closure audit FAILED: the following working-tree "
                  "headers differ from the route-D baseline (or are absent from it) "
                  "but are NOT listed in ROUTE_E_FILES:", file=sys.stderr)
            for v in violations:
                print("  " + v, file=sys.stderr)
            print("Add them to ROUTE_E_FILES so the merged package carries their "
                  "working-tree content.", file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK (all changed headers covered by ROUTE_E_FILES)")

        # ---- 1. Route E patch (Route E only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_E_FILES:
            copy_from_root(p, rel)
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: route D baseline + Route E ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in ROUTE_E_FILES:
            copy_from_root(full, rel)
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("Route E patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (route D + E)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-32s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("Route E patch", p_tar, p_n),
            ("merged full (route D + E)", full_tar, full_n),
        ]:
            print("  %-32s %d files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
