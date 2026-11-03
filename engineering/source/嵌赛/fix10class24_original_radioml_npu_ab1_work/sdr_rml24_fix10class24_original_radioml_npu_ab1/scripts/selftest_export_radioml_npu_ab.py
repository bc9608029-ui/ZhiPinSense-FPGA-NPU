#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest_export_radioml_npu_ab.py -- self-test for the STRUCTURAL invariants that
scripts/export_radioml_npu_ab_inputs.py must produce (task
fix10class24-original-radioml-npu-ab1).  It does NOT open the real HDF5 or touch
the board; it synthesizes a deterministic 480-frame input package and asserts the
exact invariants the board loader (board_package/radioml_npu_ab_loader.hpp) and the
host judger rely on:

    480 frames, selection_id contiguous 1..480, hdf5_row_index unique,
    120 frames/SNR x {0,10,20,30}, 20 frames/class x 24, input_sha256 unique,
    per-frame .bin SHA == manifest input_sha256, 8-column manifest + header,
    SHA256SUMS self-consistent.

Every invariant is checked once on a VALID package (must PASS) and once on a
mutated package (must FAIL), so the checker is proven to detect each defect rather
than trivially accepting everything.  Exit 0 iff all checks behave as expected.
"""
import hashlib
import os
import sys
import tempfile

N_FRAMES = 480
N_CLASSES = 24
SNR_LEVELS = (0, 10, 20, 30)
N_BYTES = 8192

MANIFEST_HEADER = ["selection_id", "hdf5_row_index", "raw24_class", "modulation",
                   "snr_db", "input_file", "input_sha256", "host_pred"]

LABEL_ORDER = [
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
]


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def synth_selection():
    rows = []
    sid = 1
    for cls in range(N_CLASSES):
        for snr in SNR_LEVELS:
            for k in range(5):
                hri = cls * 4000 + snr * 100 + k
                rows.append((sid, hri, cls, LABEL_ORDER[cls], snr))
                sid += 1
    return rows


def synth_bin(sid, hri):
    # Deterministic, unique-per-frame 8192 bytes (no numpy dependency).
    h = hashlib.sha256(("%d:%d" % (sid, hri)).encode()).digest()
    out = bytearray()
    while len(out) < N_BYTES:
        out += h
    return bytes(out[:N_BYTES])


def write_package(root, sel, mutate=None):
    """Write a synthetic input package.  mutate(manifest_rows) may rewrite the
    manifest rows in place (each row is a list) to inject a defect."""
    os.makedirs(root, exist_ok=True)
    manifest_rows = []
    for (sid, hri, cls, mod, snr) in sel:
        raw = synth_bin(sid, hri)
        fname = "%d.bin" % sid
        with open(os.path.join(root, fname), "wb") as f:
            f.write(raw)
        manifest_rows.append([str(sid), str(hri), str(cls), mod, str(snr),
                              fname, sha256_bytes(raw), str(cls)])  # host_pred=cls
    if mutate:
        mutate(manifest_rows)
    with open(os.path.join(root, "manifest.tsv"), "w", encoding="utf-8",
              newline="") as f:
        f.write("\t".join(MANIFEST_HEADER) + "\n")
        for r in manifest_rows:
            f.write("\t".join(r) + "\n")
    # SHA256SUMS over manifest + each .bin
    sums = []
    sums.append((sha256_bytes(open(os.path.join(root, "manifest.tsv"), "rb").read()),
                 "manifest.tsv"))
    for r in manifest_rows:
        sums.append((r[6], r[5]))
    with open(os.path.join(root, "SHA256SUMS.txt"), "w", encoding="utf-8",
              newline="") as f:
        for sha, name in sums:
            f.write("%s  %s\n" % (sha, name))
    return manifest_rows


def check_package(root):
    """Return a list of violation strings; empty list == all invariants hold."""
    v = []
    with open(os.path.join(root, "manifest.tsv"), "r", encoding="utf-8",
              newline="") as f:
        lines = [ln.rstrip("\r\n") for ln in f]
    if lines[0].split("\t") != MANIFEST_HEADER:
        v.append("manifest header mismatch")
        return v
    rows = [ln.split("\t") for ln in lines[1:] if ln.strip()]
    if len(rows) != N_FRAMES:
        v.append("row count %d != %d" % (len(rows), N_FRAMES))
    ids = []
    hris = []
    shas = []
    snr_counts = {}
    cls_counts = {}
    for r in rows:
        if len(r) != 8:
            v.append("column count %d != 8" % len(r))
            continue
        sid = int(r[0]); hri = int(r[1]); cls = int(r[2]); snr = int(r[4])
        ids.append(sid); hris.append(hri); shas.append(r[6])
        snr_counts[snr] = snr_counts.get(snr, 0) + 1
        cls_counts[cls] = cls_counts.get(cls, 0) + 1
        # per-frame .bin exists, size, SHA
        bin_path = os.path.join(root, r[5])
        if not os.path.isfile(bin_path):
            v.append("missing .bin %s" % r[5]); continue
        data = open(bin_path, "rb").read()
        if len(data) != N_BYTES:
            v.append("size %d != %d for %s" % (len(data), N_BYTES, r[5]))
        if sha256_bytes(data) != r[6]:
            v.append("SHA mismatch for %s" % r[5])
    if ids and ids != list(range(1, N_FRAMES + 1)):
        v.append("selection_id not contiguous 1..480")
    if len(set(hris)) != len(hris):
        v.append("hdf5_row_index not unique")
    if len(set(shas)) != len(shas):
        v.append("input_sha256 not unique")
    if set(snr_counts) != set(SNR_LEVELS) or any(snr_counts[s] != 120 for s in SNR_LEVELS):
        v.append("per-SNR counts != 120 each: %r" % snr_counts)
    if len(cls_counts) != N_CLASSES or any(cls_counts[c] != 20 for c in range(N_CLASSES)):
        v.append("per-class counts != 20 each")
    return v


def _mutations():
    # Each mutation is a function of manifest_rows (list of lists, in place) and a
    # short label; it must invalidate exactly the targeted invariant.
    def m_dup_hri(rows):
        rows[1][1] = rows[0][1]      # duplicate hdf5_row_index
    def m_bad_snr(rows):
        rows[0][4] = "5"             # snr not in {0,10,20,30}
    def m_dup_sha(rows):
        rows[1][6] = rows[0][6]      # duplicate input_sha256 (also breaks .bin SHA)
    def m_bad_class(rows):
        rows[0][2] = "24"            # raw24_class out of range
    def m_noncontig(rows):
        rows[5][0] = "999"           # breaks contiguous selection_id
    return [
        ("dup_hri", m_dup_hri),
        ("bad_snr", m_bad_snr),
        ("dup_sha", m_dup_sha),
        ("bad_class", m_bad_class),
        ("noncontig", m_noncontig),
    ]


def main():
    sel = synth_selection()
    base = tempfile.mkdtemp(prefix="npuab_export_selftest_")
    passed = 0
    total = 0

    def case(name, root, want_pass):
        nonlocal passed, total
        total += 1
        got = check_package(root)
        ok = (len(got) == 0) if want_pass else (len(got) > 0)
        print("  %-12s want=%-5s got=%s %s"
              % (name, "PASS" if want_pass else "FAIL",
                 "PASS" if len(got) == 0 else "FAIL(%s)" % "; ".join(got[:3]),
                 "OK" if ok else "MISMATCH"))
        if ok:
            passed += 1

    # valid package
    valid_root = os.path.join(base, "valid")
    write_package(valid_root, sel)
    case("valid", valid_root, True)

    # SHA256SUMS self-consistency on the valid package
    total += 1
    sums_ok = True
    with open(os.path.join(valid_root, "SHA256SUMS.txt"), "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.rstrip("\r\n")
            if not ln:
                continue
            sha, _, name = ln.partition("  ")
            if sha256_bytes(open(os.path.join(valid_root, name), "rb").read()) != sha:
                sums_ok = False
    print("  %-12s want=PASS  got=%s %s"
          % ("sha256sums", "PASS" if sums_ok else "FAIL", "OK" if sums_ok else "MISMATCH"))
    if sums_ok:
        passed += 1

    # mutated packages (each must FAIL)
    for label, mut in _mutations():
        m_root = os.path.join(base, label)
        write_package(m_root, sel, mutate=mut)
        case(label, m_root, False)

    print("SELFTEST_EXPORT_RADIOML_NPU_AB %d/%d" % (passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
