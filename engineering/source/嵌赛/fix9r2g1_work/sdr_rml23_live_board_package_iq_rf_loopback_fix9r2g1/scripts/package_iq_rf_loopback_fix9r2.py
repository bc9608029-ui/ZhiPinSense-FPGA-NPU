#!/usr/bin/env python3
"""Package RML23 Route F fix9r2 -- the training-frame search-window root-cause fix.

fix9r1 (sdr_rml23_live_board_package_iq_rf_loopback_fix9r1.tar.gz, sha
306873e100a8238e0adfe8c38b8a202be4adc4a542144f3b966ee91c50b0a93d) is the Route F
"per-file recovery" increment whose ONLY defect was proven on the board: its
receiver searched the preamble over the first 4096 samples of the capture, while
the TX is a 59904-sample CYCLIC buffer -- so the preamble is inside that window
only ~6.8% of the time and the other ~93% the search locks onto noise (measured
training_corr_avg=0.110172 matches the expected noise lock 0.127).

fix9r2 fixes the search, not the RF math, and does NOT resume the paused fix10
(double-SDR).  Its Task R1-R9 changes (see docs/...FIX9R2_AUDIT.md):

  R1/R2  byte-level TX provenance + an independent TX-frame verifier, fail-closed
         BEFORE any push (iq_rf_tx_provenance.hpp; pluto_device.hpp/pluto_device_libiio.cpp
         record the iio_buffer_push requested/returned/ok bytes);
  R3     training-frame design audit (version/seed recorded, iq_rf_training_frame.hpp);
  R4     explicit cyclic frame layout + capture >= 2 periods + full-capture search
         (iq_rf_frame_layout.hpp; transfer captures iqrflayout::capture_complex);
  R5     the SHARED recovery core iq_rf_sync_recovery.hpp (fix10 must reuse this one
         core), with math sign conventions in iq_rf_frame_layout.hpp;
  R6     typed valid semantics: estimate_computed vs estimate_valid, an 11-value
         Failure enum, failure tokens (never "valid=1 means the function returned a
         number");
  R7     host tests test_iq_rf_loopback_23class_fix9r2.cpp (15 scenarios / 66 checks);
  R8/R9  board-only (2-sample diagnostic, then 46-sample regression) -- NOT run here.

It touches NOTHING outside Route F + the fix9r2 wiring: no model / labels / 24->23
merge rules / golden / production preprocessing / production read_rx libiio path /
RTL / XDC / bitstream / Flash; fix9's verified internal digital-loopback and
same-machine RF paths are reused by #include only; the RF safety ceiling
(kSafeTxCeilingDb=-40.0 / kSafeTxAttenDb=-89.75) is unchanged.

IMPORTANT (fix10 pause): Route G fix10 is PAUSED and its on-disk files are preserved.
Three fix9r2 wiring files carry BOTH fix9r2 and fix10 edits on disk
(sdr_adapter/pluto_device.hpp host-test CFO/SRO injection, host_tests/build_host_tests.sh
and host_tests/run_tests.sh the two fix10 test entries).  This packager reconstructs
those three to their FIX9R2-ONLY content by removing the fix10 edits (the fix10
on-disk files are never touched), so the produced package is exactly fix9r1 + fix9r2.

Produces, under dist/ (leaving every earlier package untouched, INCLUDING the fix9r1
package it builds on):

  1. sdr_rml23_live_iq_rf_loopback_fix9r2_patch.tar.gz          (Route F fix9r2 only)
  2. sdr_rml23_live_board_package_iq_rf_loopback_fix9r2.tar.gz  (fix9r1 full + fix9r2)

Each tarball is self-contained: a top directory holding the changed files plus a
SHA256SUMS file in the repo's `HASH *relpath` convention (sha256sum -b), so
`cd <topdir> && sha256sum -c <SUMS>` verifies it.  Nothing in dist/ is overwritten.
Packaging permissions (§21): directories 0755 / *.sh 0755 / everything else 0644;
0666/0777 never used (the fix9r1 permission correction is retained).

A dependency-closure audit walks the transitive #include closure of every fix9r2
C/C++ file AGAINST the clean full tree (fix9r1 baseline + fix9r2-only files) and
ABORTS if any resolved header differs from the fix9r1 baseline but is not in
ROUTE_F_FIX9R2_FILES.

stdlib only.  Run with:  python3 scripts/package_iq_rf_loopback_fix9r2.py
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
BASE_TAR = os.path.join(DIST, "sdr_rml23_live_board_package_iq_rf_loopback_fix9r1.tar.gz")
BASE_DIR = "sdr_rml23_live_board_package_iq_rf_loopback_fix9r1"
BASE_SHA = "306873e100a8238e0adfe8c38b8a202be4adc4a542144f3b966ee91c50b0a93d"

PATCH_NAME = "sdr_rml23_live_iq_rf_loopback_fix9r2_patch"
PATCH_SUMS_NAME = "IQ_RF_LOOPBACK_FIX9R2_PATCH_SHA256SUMS.txt"
FULL_NAME = "sdr_rml23_live_board_package_iq_rf_loopback_fix9r2"
FULL_SUMS_NAME = "SHA256SUMS.txt"

# fix9r2 NEW files (copied verbatim from the working tree).
ROUTE_F_FIX9R2_NEW_FILES = [
    "board_package/iq_rf_frame_layout.hpp",                 # NEW (Task R4/R5)
    "board_package/iq_rf_sync_recovery.hpp",                # NEW (Task R5/R6 shared core)
    "board_package/iq_rf_tx_provenance.hpp",                # NEW (Task R1/R2)
    "host_tests/test_iq_rf_loopback_23class_fix9r2.cpp",    # NEW (Task R7)
    "scripts/package_iq_rf_loopback_fix9r2.py",             # NEW (this packager)
    "docs/M29_RML23_STAGE_H_F_IQ_RF_LOOPBACK_FIX9R2_AUDIT.md",  # NEW (audit + record)
]

# fix9r2 MODIFIED files.  The first three carry fix10 edits on disk and are
# reconstructed to fix9r2-only content by _FIX10_REMOVAL; the rest are fix9r2-only
# and copied verbatim.
ROUTE_F_FIX9R2_MODIFIED_FILES = [
    "sdr_adapter/pluto_device.hpp",                         # MODIFIED (R1 provenance; strip fix10)
    "host_tests/build_host_tests.sh",                       # MODIFIED (build fix9r2 test; strip fix10)
    "host_tests/run_tests.sh",                              # MODIFIED (run fix9r2 test; strip fix10)
    "board_package/iq_rf_per_frame_recovery.hpp",           # MODIFIED (thin shim -> shared core)
    "board_package/iq_rf_training_frame.hpp",               # MODIFIED (R3 version/seed)
    "board_package/iq_rf_loopback_transfer_fix9r.hpp",      # MODIFIED (2-period capture + R1/R2)
    "board_package/iq_rf_loopback_23class_fix9r.hpp",       # MODIFIED (shared core + valid semantics)
    "sdr_adapter/pluto_device_libiio.cpp",                  # MODIFIED (R1 push provenance)
]

ROUTE_F_FIX9R2_FILES = ROUTE_F_FIX9R2_NEW_FILES + ROUTE_F_FIX9R2_MODIFIED_FILES


# ---------------------------------------------------------------------------
# fix10 removal: each transform returns the fix9r2-only text of one on-disk file.
# ---------------------------------------------------------------------------
def _strip_fix10_pluto_device(text):
    """Remove the Route G (fix10) host-test CFO/SRO injection from pluto_device.hpp,
    leaving the fix9r2 R1 provenance intact."""
    # 1. the fs/sro_scale/cfo_rad/apply_sro/apply_cfo prologue
    old = ("            const double fs = (rx_sample_rate_ > 0)\n"
           "                                  ? static_cast<double>(rx_sample_rate_) : 2560000.0;\n"
           "            const double sro_scale = 1.0 + rf_sro_ppm * 1e-6;\n"
           "            const double cfo_rad = 2.0 * 3.14159265358979323846 * rf_cfo_hz / fs;\n"
           "            const bool apply_sro = (rf_sro_ppm != 0.0);\n"
           "            const bool apply_cfo = (rf_cfo_hz != 0.0);\n"
           "            for (std::size_t k = 0; k < n; ++k) {\n")
    assert text.count(old) == 1, "pluto_device.hpp fix10 prologue not unique/found"
    text = text.replace(old, "            for (std::size_t k = 0; k < n; ++k) {\n")

    # 2. the SRO linear-interpolation (restore the simple cyclic source read)
    old = ("                if (tx_on) {\n"
           "                    // Route G (fix10): SRO.  A nonzero rf_sro_ppm models an\n"
           "                    // independent TX clock -- the received sample at receiver index\n"
           "                    // m corresponds to transmitter sample m*(1+sro).  Fractional\n"
           "                    // source index -> linear interpolation.\n"
           "                    double xI, xQ;\n"
           "                    if (apply_sro) {\n"
           "                        const double srcf =\n"
           "                            (static_cast<double>(rx_tone_pos_) +\n"
           "                             static_cast<double>(k) +\n"
           "                             static_cast<double>(rf_delay)) * sro_scale;\n"
           "                        const double floor_src = std::floor(srcf);\n"
           "                        const std::size_t s0 = static_cast<std::size_t>(\n"
           "                            static_cast<std::uint64_t>(floor_src) % N);\n"
           "                        const std::size_t s1 = (s0 + 1) % N;\n"
           "                        const double frac = srcf - floor_src;\n"
           "                        const double xI0 = static_cast<double>(w[s0 * 2 + 0]);\n"
           "                        const double xQ0 = static_cast<double>(w[s0 * 2 + 1]);\n"
           "                        const double xI1 = static_cast<double>(w[s1 * 2 + 0]);\n"
           "                        const double xQ1 = static_cast<double>(w[s1 * 2 + 1]);\n"
           "                        xI = xI0 + frac * (xI1 - xI0);\n"
           "                        xQ = xQ0 + frac * (xQ1 - xQ0);\n"
           "                    } else {\n"
           "                        const std::size_t src = (rx_tone_pos_ + k + rf_delay) % N;\n"
           "                        xI = static_cast<double>(w[src * 2 + 0]);\n"
           "                        xQ = static_cast<double>(w[src * 2 + 1]);\n"
           "                    }\n"
           "                    I = xI * gr - xQ * gi;\n")
    new = ("                if (tx_on) {\n"
           "                    const std::size_t src = (rx_tone_pos_ + k + rf_delay) % N;\n"
           "                    const double xI = static_cast<double>(w[src * 2 + 0]);\n"
           "                    const double xQ = static_cast<double>(w[src * 2 + 1]);\n"
           "                    I = xI * gr - xQ * gi;\n")
    assert text.count(old) == 1, "pluto_device.hpp fix10 SRO block not unique/found"
    text = text.replace(old, new)

    # 3. the CFO rotation
    old = ("                // Route G (fix10): CFO.  Rotate the whole received sample (signal +\n"
           "                // noise) by a phase ramp in the absolute sample index, modelling two\n"
           "                // independent LOs.  (Rotating pure TX-off noise is a no-op, so the\n"
           "                // negative-control noise floor is unchanged.)\n"
           "                if (apply_cfo) {\n"
           "                    const double theta = cfo_rad * static_cast<double>(rx_tone_pos_ + k);\n"
           "                    const double cth = std::cos(theta);\n"
           "                    const double sth = std::sin(theta);\n"
           "                    const double Ir = I * cth - Q * sth;\n"
           "                    const double Qi = I * sth + Q * cth;\n"
           "                    I = Ir;\n"
           "                    Q = Qi;\n"
           "                }\n"
           "                rx_scratch_[k * 2 + 0] = static_cast<std::int16_t>(\n")
    assert text.count(old) == 1, "pluto_device.hpp fix10 CFO block not unique/found"
    text = text.replace(old, "                rx_scratch_[k * 2 + 0] = static_cast<std::int16_t>(\n")

    # 4. the rf_cfo_hz / rf_sro_ppm field declarations
    old = ("    // Route G (fix10) test injection (host-test only, default off; the real board\n"
           "    // device is unaffected): model two INDEPENDENT Plutos.  rf_cfo_hz adds a carrier\n"
           "    // frequency offset (the received sample at absolute index m is rotated by\n"
           "    // exp(j*2*pi*cfo*m/fs)); rf_sro_ppm adds a sampling-rate offset (the received\n"
           "    // sample at index m corresponds to transmitter sample m*(1 + sro_ppm/1e6),\n"
           "    // linearly interpolated).  Together they are what the RX runner's CFO/SRO\n"
           "    // estimators must recover before the payload is extracted.\n"
           "    double rf_cfo_hz = 0.0;\n"
           "    double rf_sro_ppm = 0.0;\n")
    assert text.count(old) == 1, "pluto_device.hpp fix10 field declarations not unique/found"
    text = text.replace(old, "")

    for tok in ("rf_cfo_hz", "rf_sro_ppm", "apply_sro", "apply_cfo", "sro_scale", "cfo_rad"):
        assert tok not in text, "pluto_device.hpp still contains fix10 token: %s" % tok
    return text


def _strip_fix10_build(text):
    """Remove the two fix10 test build entries from build_host_tests.sh."""
    old = ('echo "== build test_iq_external_rf_rx_23class =="\n'
           '$CXX $FLAGS test_iq_external_rf_rx_23class.cpp -o bin/test_iq_external_rf_rx_23class\n'
           '\n'
           'echo "== build test_pluto_external_tx =="\n'
           '$CXX $FLAGS test_pluto_external_tx.cpp -o bin/test_pluto_external_tx\n'
           '\n')
    assert text.count(old) == 1, "build_host_tests.sh fix10 entries not unique/found"
    text = text.replace(old, "")

    old = 'test_iq_rf_loopback_23class_fix9r2,test_iq_external_rf_rx_23class,test_pluto_external_tx}'
    assert text.count(old) == 1, "build_host_tests.sh fix10 OK echo not unique/found"
    text = text.replace(old, 'test_iq_rf_loopback_23class_fix9r2}')

    assert "iq_external_rf_rx" not in text and "pluto_external_tx" not in text
    assert "test_iq_rf_loopback_23class_fix9r2" in text
    return text


def _strip_fix10_run(text):
    """Remove the two fix10 test run entries from run_tests.sh."""
    old = ('./bin/test_iq_rf_loopback_23class_fix9r2 || rc=1\n'
           './bin/test_iq_external_rf_rx_23class || rc=1\n'
           './bin/test_pluto_external_tx || rc=1\n')
    assert text.count(old) == 1, "run_tests.sh fix10 entries not unique/found"
    text = text.replace(old, './bin/test_iq_rf_loopback_23class_fix9r2 || rc=1\n')
    assert "iq_external_rf_rx" not in text and "pluto_external_tx" not in text
    assert "test_iq_rf_loopback_23class_fix9r2" in text
    return text


_FIX10_REMOVAL = {
    "sdr_adapter/pluto_device.hpp": _strip_fix10_pluto_device,
    "host_tests/build_host_tests.sh": _strip_fix10_build,
    "host_tests/run_tests.sh": _strip_fix10_run,
}


def _fix9r2_content(rel):
    """Return the fix9r2-only content of a file (fix10 stripped for MODIFIED files)."""
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
    """Deterministic tar.gz with EXPLICIT member modes (dir/.sh -> 0755, else 0644).

    Retains the fix9r1 permission correction: directory members are emitted
    explicitly (0755), scripts are 0755, everything else 0644; 0666/0777 never used.
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
    """Fail-closed closure audit over the CLEAN full tree.

    Walk the transitive #include closure of every fix9r2 C/C++ file (read from
    full_dir, which is fix9r1 baseline + fix9r2-only content).  For each resolved
    header whose bytes DIFFER from the fix9r1 baseline (or are absent from it),
    require it to be in ROUTE_F_FIX9R2_FILES.  Returns a sorted list of violations.
    """
    base_sha = {}
    for dirpath, dirnames, filenames in os.walk(base_dir):
        dirnames.sort()
        for name in filenames:
            full = os.path.join(dirpath, name)
            base_sha[_rel_of(base_dir, full)] = sha256_of(full)

    fix9r2_set = set(ROUTE_F_FIX9R2_FILES)
    violations = set()
    seen = set()
    queue = [rel for rel in ROUTE_F_FIX9R2_FILES if rel.endswith(_CPP_EXT)]

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
                if sha256_of(resolved) != base_sha[rrel] and rrel not in fix9r2_set:
                    violations.add(rrel)
            else:
                if rrel not in fix9r2_set:
                    violations.add(rrel)
            if resolved not in seen:
                queue.append(rrel)

    return sorted(violations)


def verify_content_consistency(base, full):
    """Prove fix9r2 content == fix9r1 content except the fix9r2 files + SUMS.

    Returns (unchanged, changed, extra).  changed must be exactly the fix9r2 files
    that already exist in fix9r1 (the MODIFIED set); extra must be exactly the NEW
    set (minus SHA256SUMS.txt which is regenerated).
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

    new_set = set(ROUTE_F_FIX9R2_NEW_FILES)
    mod_set = set(ROUTE_F_FIX9R2_MODIFIED_FILES)
    changed_paths = set(rel for rel, _ in changed)
    extra = sorted(set(full_map) - set(base_map))
    # extra (files present in full but not base) must be exactly the NEW set minus SUMS.
    expected_extra = new_set - {"SHA256SUMS.txt"} - set(["SHA256SUMS.txt"])
    return unchanged, changed, extra, changed_paths, mod_set, expected_extra


def main():
    if not os.path.exists(BASE_TAR):
        sys.exit("missing baseline package: %s" % BASE_TAR)
    actual = sha256_of(BASE_TAR)
    if actual != BASE_SHA:
        sys.exit("baseline package SHA mismatch:\n  expected %s\n  got      %s" % (BASE_SHA, actual))

    for rel in ROUTE_F_FIX9R2_FILES:
        if not os.path.exists(os.path.join(ROOT, rel)):
            sys.exit("missing working-tree file: %s" % rel)

    # Pre-compute the fix9r2-only content of every file (stripping fix10 from the
    # three shared wiring files) and fail-closed on any drift.
    content = {}
    for rel in ROUTE_F_FIX9R2_FILES:
        content[rel] = _fix9r2_content(rel)

    work = tempfile.mkdtemp(prefix="pkg_rfloop_fix9r2_")
    try:
        base = os.path.join(work, BASE_DIR)
        with tarfile.open(BASE_TAR, "r:gz") as t:
            t.extractall(work)

        # ---- clean full tree: fix9r1 baseline + fix9r2-only files ----
        full = os.path.join(work, FULL_NAME)
        shutil.copytree(base, full)
        os.remove(os.path.join(full, "SHA256SUMS.txt"))  # regenerated below
        for rel in ROUTE_F_FIX9R2_FILES:
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
        print("content-consistency: OK (%d fix9r1 files byte-identical, "
              "%d modified, +%d new)" % (len(unchanged), len(changed_paths), len(extra)))

        # ---- dependency-closure audit (fail-closed) ----
        violations = audit_dependency_closure(full, base)
        if violations:
            print("dependency-closure audit FAILED: headers differ from the fix9r1 "
                  "baseline (or are absent from it) but are NOT listed in "
                  "ROUTE_F_FIX9R2_FILES:", file=sys.stderr)
            for v in violations:
                print("  " + v, file=sys.stderr)
            sys.exit(1)
        print("dependency-closure audit: OK (all changed headers covered by ROUTE_F_FIX9R2_FILES)")

        # ---- 1. fix9r2 patch (fix9r2 only) ----
        p = os.path.join(work, PATCH_NAME)
        os.makedirs(p, exist_ok=True)
        for rel in ROUTE_F_FIX9R2_FILES:
            write_bytes(os.path.join(p, rel.replace("/", os.sep)),
                        content[rel].encode("utf-8"))
        p_n = write_sums(p, PATCH_SUMS_NAME)
        p_tar = os.path.join(DIST, PATCH_NAME + ".tar.gz")
        make_tar(p, p_tar)
        shutil.copy2(os.path.join(p, PATCH_SUMS_NAME), os.path.join(DIST, PATCH_SUMS_NAME))

        # ---- 2. merged full package: fix9r1 baseline + fix9r2 ----
        full_n = write_sums(full, FULL_SUMS_NAME)
        full_tar = os.path.join(DIST, FULL_NAME + ".tar.gz")
        make_tar(full, full_tar)
        shutil.copy2(os.path.join(full, FULL_SUMS_NAME),
                     os.path.join(DIST, FULL_NAME + ".SHA256SUMS.txt"))

        # ---- self-check ----
        print("== self-check ==")
        for label, tar, sums, top in [
            ("fix9r2 patch", p_tar, PATCH_SUMS_NAME, PATCH_NAME),
            ("merged full (fix9r1 + fix9r2)", full_tar, FULL_SUMS_NAME, FULL_NAME),
        ]:
            ok, total, good = verify_tar(tar, sums, top)
            print("  %-32s files=%d ok=%d %s" % (label, total, good, "PASS" if ok else "FAIL"))
            if not ok:
                sys.exit(1)

        print("== summary ==")
        for label, tar, n in [
            ("fix9r2 patch", p_tar, p_n),
            ("merged full (fix9r1 + fix9r2)", full_tar, full_n),
        ]:
            print("  %-32s %d content-files  sha256=%s" % (label, n, sha256_of(tar)))
            print("  %s" % tar)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
