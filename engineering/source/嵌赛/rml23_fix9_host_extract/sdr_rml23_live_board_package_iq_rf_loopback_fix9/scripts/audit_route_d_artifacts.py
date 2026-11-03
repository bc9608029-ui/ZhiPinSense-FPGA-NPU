#!/usr/bin/env python3
"""audit_route_d_artifacts.py -- fix8 Task D: Route D frozen artifact audit.

Reads a Route D round-trip artifact directory (written by the board's route-D
runner: --phase=synthetic-iq --source=radioml
--inject-point=raw-rx-reconstructed, e.g. /root/rml23_route_d_scale128_* ) and
verifies, WITHOUT opening the NPU or any device:

  1. manifest columns  -- roundtrip_manifest.tsv has the exact 13-column header
     the board writes, and every data row has exactly 13 tab-separated fields,
     contiguous index 0..N-1, class_index in 0..23, hdf5_label == class_index,
     non-empty class_name, and a 64-hex original_sha256;
  2. 6-file existence -- each of the 6 referenced artifact files per row
     (original / interpolated / quantized / recovered / raw24_a / raw24_d) is a
     flat basename that resolves to a readable regular file;
  3. no dangling symlinks -- no symlink anywhere under the artifact dir resolves
     to a missing target;
  4. correct size/SHA -- the fixed-size files have the exact production sizes
     (original=8192, recovered=8192, raw24_*=96 bytes), the interpolated file is
     exactly (1024 + 2*832) * 20 * 8 = 430080 bytes and the quantized file exactly
     half that (215040 bytes, == 4 bytes per complex), and the original file's
     SHA-256 matches the manifest original_sha256 column;
  5. recovered tensor exactly 8192 bytes;
  6. quantized size == complex count (quant_bytes/4 == interp_bytes/8).

Verifies SIZE/SHA/integrity only.  It NEVER issues a classification or accuracy
verdict, never opens a device, and never runs the NPU.

Outputs one machine-parseable line
  ROUTE_D_ARTIFACT_AUDIT result=PASS|FAIL [missing=N] [dangling=N]
      [size_mismatch=N] [sha_mismatch=N] [manifest=N]
(the four spec categories missing/dangling/size_mismatch/sha_mismatch, plus
`manifest` for structural manifest faults).  A nonzero count in any category =>
result=FAIL.

Pure stdlib.  Run isolated:  python -I audit_route_d_artifacts.py --self-test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

# ---------------------------------------------------------------------------
# Frozen production constants (== chain_common.hpp / synthetic_iq_roundtrip.hpp).
# ---------------------------------------------------------------------------
N_SAMPLES = 1024                       # chain::kFrameComplex
K_TENSOR_BYTES = 8192                  # chain::kTensorBytes (2048 fp32)
K_LOGITS_FLOATS = 24                   # NpuClassifier24 raw output
K_LOGITS_BYTES = K_LOGITS_FLOATS * 4   # 96
K_GUARD = 832                          # syniq_rt::kGuard (production, not CLI)
K_INTERP_FACTOR = 20                   # syniq_rt::kInterpFactor (128k -> 2.56M)

# interpolate_20x output length = (1024 + 2*guard) * 20 complex samples.
INTERP_COMPLEX = (N_SAMPLES + 2 * K_GUARD) * K_INTERP_FACTOR   # 53760
INTERP_BYTES = INTERP_COMPLEX * 8                              # 430080 (2 fp32/complex)
QUANT_BYTES = INTERP_COMPLEX * 4                               # 215040 (2 int16/complex)

# roundtrip_manifest.tsv header the board writes (13 columns).
EXPECTED_HEADER = [
    "index", "source_index", "hdf5_label", "snr_db", "class_index", "class_name",
    "original_file", "interp_file", "quant_file", "recovered_file",
    "raw24_a_file", "raw24_d_file", "original_sha256",
]

# Column -> exact byte size.  interp/quant sizes follow from the frozen guard and
# 20x factor; the quant/interp ratio (== complex count) is also checked directly.
COLUMN_SIZE = {
    "original_file": K_TENSOR_BYTES,
    "interp_file": INTERP_BYTES,
    "quant_file": QUANT_BYTES,
    "recovered_file": K_TENSOR_BYTES,
    "raw24_a_file": K_LOGITS_BYTES,
    "raw24_d_file": K_LOGITS_BYTES,
}

# The six per-frame artifact file kinds (spec item 2: "6-class file existence").
FILE_COLUMNS = [
    "original_file", "interp_file", "quant_file", "recovered_file",
    "raw24_a_file", "raw24_d_file",
]


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def is_flat_basename(name: str) -> bool:
    return bool(name) and "/" not in name and "\\" not in name and ".." not in name


def find_dangling_symlinks(root: str):
    """Yield the full path of every symlink under `root` whose target is missing."""
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        for name in dirnames + filenames:
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                if not os.path.exists(full):
                    yield full


def audit(out_dir: str):
    """Return (ok, counts, details) where counts is a dict category->int and
    details is a list of human-readable diagnostic strings."""
    counts = {"missing": 0, "dangling": 0, "size_mismatch": 0,
              "sha_mismatch": 0, "manifest": 0}
    details = []
    classes_found = {}

    def note(cat, msg):
        counts[cat] += 1
        details.append("[%s] %s" % (cat, msg))

    # ---- 3. no dangling symlinks (scan the whole tree first, cheap) ----------
    for bad in find_dangling_symlinks(out_dir):
        note("dangling", "dangling symlink: %s" % bad)

    # ---- 1. manifest columns ------------------------------------------------
    mpath = os.path.join(out_dir, "roundtrip_manifest.tsv")
    if not os.path.isfile(mpath):
        note("manifest", "missing roundtrip_manifest.tsv in %s" % out_dir)
        return False, counts, details

    with open(mpath, "r", encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        body = [ln.rstrip("\n") for ln in f if ln.rstrip("\n")]

    if header != EXPECTED_HEADER:
        note("manifest", "manifest header mismatch: got %r" % (header,))
    if not body:
        note("manifest", "manifest has zero data rows")

    rows = []
    for idx, line in enumerate(body):
        p = line.split("\t")
        if len(p) != len(EXPECTED_HEADER):
            note("manifest", "row %d has %d fields, want %d"
                 % (idx, len(p), len(EXPECTED_HEADER)))
            continue
        rows.append(p)

    # index contiguity / label cross-check / class range (mirrors load_route_a).
    expected_index = 0
    for p in rows:
        try:
            index = int(p[0])
            source_index = int(p[1])
            hdf5_label = int(p[2])
            class_index = int(p[4])
        except ValueError:
            note("manifest", "non-integer index/label in row starting %r" % (p[0],))
            expected_index += 1
            continue

        if index != expected_index:
            note("manifest", "non-contiguous index %d (expected %d)"
                 % (index, expected_index))
        if not (0 <= class_index < 24):
            note("manifest", "index %d class_index %d out of range [0,24)"
                 % (index, class_index))
        if hdf5_label != class_index:
            note("manifest", "index %d hdf5_label %d != class_index %d"
                 % (index, hdf5_label, class_index))
        if not p[5]:
            note("manifest", "index %d empty class_name" % index)
        classes_found[p[5]] = classes_found.get(p[5], 0) + 1
        expected_index += 1

    # ---- 2/4/5/6. per-frame file existence + size + SHA ---------------------
    for p in rows:
        try:
            index = int(p[0])
        except ValueError:
            continue
        sha_field = p[12]

        for col in FILE_COLUMNS:
            fname = p[EXPECTED_HEADER.index(col)]
            if not is_flat_basename(fname):
                note("manifest", "index %d unsafe %s filename %r"
                     % (index, col, fname))
                continue
            path = os.path.join(out_dir, fname)
            if not os.path.isfile(path):
                note("missing", "index %d %s not found: %s" % (index, col, fname))
                continue

            actual = os.path.getsize(path)
            want = COLUMN_SIZE[col]
            if actual != want:
                note("size_mismatch", "index %d %s size %d != %d (%s)"
                     % (index, col, actual, want, fname))

        # recovered tensor exactly 8192 bytes (also covered by COLUMN_SIZE, but
        # reported explicitly per spec item 5).
        rec_name = p[EXPECTED_HEADER.index("recovered_file")]
        rec_path = os.path.join(out_dir, rec_name)
        if is_flat_basename(rec_name) and os.path.isfile(rec_path):
            if os.path.getsize(rec_path) != K_TENSOR_BYTES:
                note("size_mismatch", "index %d recovered tensor != 8192 bytes"
                     % index)

        # quantized size == complex count: quant_bytes/4 == interp_bytes/8.
        q_name = p[EXPECTED_HEADER.index("quant_file")]
        i_name = p[EXPECTED_HEADER.index("interp_file")]
        q_path = os.path.join(out_dir, q_name)
        i_path = os.path.join(out_dir, i_name)
        if (is_flat_basename(q_name) and is_flat_basename(i_name)
                and os.path.isfile(q_path) and os.path.isfile(i_path)):
            qsz = os.path.getsize(q_path)
            isz = os.path.getsize(i_path)
            if qsz % 4 != 0 or isz % 8 != 0 or qsz // 4 != isz // 8:
                note("size_mismatch",
                     "index %d quantized complex count (%d) != interpolated complex "
                     "count (%d)" % (index, qsz // 4, isz // 8))

        # SHA-256 of the original file vs the manifest column (spec item 4).
        orig_name = p[EXPECTED_HEADER.index("original_file")]
        if len(sha_field) != 64 or any(c not in "0123456789abcdef" for c in sha_field):
            note("manifest", "index %d original_sha256 not 64 hex" % index)
        elif is_flat_basename(orig_name):
            orig_path = os.path.join(out_dir, orig_name)
            if os.path.isfile(orig_path):
                got = sha256_file(orig_path)
                if got != sha_field:
                    note("sha_mismatch", "index %d original_file SHA %s != manifest %s"
                         % (index, got, sha_field))

    ok = all(v == 0 for v in counts.values())
    return ok, counts, details


def format_verdict(ok, counts):
    parts = ["result=%s" % ("PASS" if ok else "FAIL")]
    for cat in ("missing", "dangling", "size_mismatch", "sha_mismatch", "manifest"):
        if counts[cat] != 0 or not ok:
            parts.append("%s=%d" % (cat, counts[cat]))
    return "ROUTE_D_ARTIFACT_AUDIT " + " ".join(parts)


def _make_fixture(root, *, drop=None, corrupt_size=None, corrupt_sha=None,
                  dangling=False, bad_header=False):
    """Build a minimal-but-real Route D artifact dir (1 frame) for the self-test.

    Sizes and SHA follow the production constants; `drop` removes a file,
    `corrupt_size` overwrites a file with the wrong size, `corrupt_sha` rewrites
    the manifest sha, `dangling` adds a dangling symlink, `bad_header` rewrites
    the header.
    """
    os.makedirs(root, exist_ok=True)
    rng = os.urandom

    files = {
        "original_file": K_TENSOR_BYTES,
        "interp_file": INTERP_BYTES,
        "quant_file": QUANT_BYTES,
        "recovered_file": K_TENSOR_BYTES,
        "raw24_a_file": K_LOGITS_BYTES,
        "raw24_d_file": K_LOGITS_BYTES,
    }
    blobs = {}
    for col, sz in files.items():
        blob = rng(sz)
        blobs[col] = blob
        with open(os.path.join(root, col), "wb") as f:
            f.write(blob)
    orig_sha = hashlib.sha256(blobs["original_file"]).hexdigest()

    header = "\t".join(EXPECTED_HEADER)
    if bad_header:
        header = header.replace("recovered_file", "recov_file", 1)
    row = ["0", "12345", "4", "20.0", "4", "QPSK",
           "original_file", "interp_file", "quant_file", "recovered_file",
           "raw24_a_file", "raw24_d_file",
           ("0" * 64) if corrupt_sha else orig_sha]
    with open(os.path.join(root, "roundtrip_manifest.tsv"), "w", encoding="utf-8") as f:
        f.write(header + "\n")
        f.write("\t".join(row) + "\n")

    if drop is not None:
        os.remove(os.path.join(root, drop))
    if corrupt_size is not None:
        with open(os.path.join(root, corrupt_size), "wb") as f:
            f.write(rng(123))
    if dangling:
        os.symlink(os.path.join(root, "does_not_exist"),
                   os.path.join(root, "dangling_link"))


def self_test() -> int:
    import shutil
    import tempfile

    n_pass = 0
    n_skip = 0
    tmp = tempfile.mkdtemp(prefix="route_d_audit_")

    def run_case(name, want_ok, want_cat, **kw):
        nonlocal n_pass, n_skip
        d = os.path.join(tmp, name)
        try:
            _make_fixture(d, **kw)
        except OSError as e:
            # e.g. Windows cannot create a symlink without privilege/dev-mode;
            # that is a host limitation, not an auditor defect -- skip the case.
            n_skip += 1
            print("  SKIP %-26s (cannot build fixture on this host: %s)"
                  % (name, e.strerror or e))
            shutil.rmtree(d, ignore_errors=True)
            return
        ok, counts, details = audit(d)
        cat_ok = True if want_cat is None else (counts.get(want_cat, 0) > 0)
        good = (ok == want_ok) and cat_ok
        if good:
            n_pass += 1
            print("  OK  %-28s -> result=%s (%s)" %
                  (name, "PASS" if ok else "FAIL", want_cat or "ok"))
        else:
            print("  BAD %-28s -> result=%s counts=%r" % (name, ok, counts))
        shutil.rmtree(d, ignore_errors=True)

    run_case("clean", want_ok=True, want_cat=None)
    run_case("drop_file", want_ok=False, want_cat="missing", drop="quant_file")
    run_case("bad_size", want_ok=False, want_cat="size_mismatch",
             corrupt_size="recovered_file")
    run_case("bad_sha", want_ok=False, want_cat="sha_mismatch", corrupt_sha=True)
    run_case("dangling_link", want_ok=False, want_cat="dangling", dangling=True)
    run_case("bad_header", want_ok=False, want_cat="manifest", bad_header=True)

    shutil.rmtree(tmp, ignore_errors=True)
    total = 6
    print("self-test: %d/%d correct%s" %
          (n_pass, total - n_skip, (" (%d skipped)" % n_skip) if n_skip else ""))
    return 0 if n_pass == (total - n_skip) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=None,
                    help="Route D artifact dir (holds roundtrip_manifest.tsv)")
    ap.add_argument("--json", default=None, help="write full machine-readable JSON")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if not args.out_dir:
        ap.error("--out-dir is required unless --self-test is given")

    ok, counts, details = audit(args.out_dir)
    print(format_verdict(ok, counts))
    for d in details:
        print("  " + d)
    print("  categories=%s" % json.dumps(counts, sort_keys=True))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"result": "PASS" if ok else "FAIL",
                       "counts": counts, "details": details}, f, indent=2)
        print("  wrote %s" % args.json)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
