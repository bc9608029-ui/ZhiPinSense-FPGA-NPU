#!/usr/bin/env python3
"""Ground-truth diff: rxrecovery1 tree vs (rxfrontend full, rxresidual_audit1 tree)."""
import os, sys, hashlib, tarfile, tempfile, shutil

BASE_FULL_TAR = "/mnt/f/嵌赛/fix10class24_dualsdr2_work/sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2/dist/sdr_rml24_fix10class24_bf16_dualsdr2_rxfrontend_full.tar.gz"
FULL_NAME = "sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2"
RXRES_TREE = "/mnt/f/嵌赛/fix10class24_rxresidual_audit1_work/sdr_rml24_fix10class24_rxresidual_audit1"
RXREC_TREE = "/mnt/f/嵌赛/fix10class24_dualsdr_rxrecovery1_work/sdr_rml24_fix10class24_dualsdr_rxrecovery1"

EXCLUDED_DIRS = {"host_tests/bin", "host_tests/__pycache__", "host_tools/__pycache__",
                 "scripts/__pycache__", "dist", ".git",
                 "host_tools/.build_burst_cache", "host_tools/.replay24_cache",
                 "results"}
EXCLUDED_FILES = {"host_tests/build_host_tests.log", "host_tests/run_tests.log"}
SUMS = "SHA256SUMS.txt"

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

def walk(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn
                       if os.path.relpath(os.path.join(dp, d), root).replace(os.sep, "/")
                       not in EXCLUDED_DIRS)
        for name in fn:
            rel = os.path.relpath(os.path.join(dp, name), root).replace(os.sep, "/")
            if rel in EXCLUDED_FILES or rel == SUMS:
                continue
            out[rel] = sha(os.path.join(dp, name))
    return out

def diff(a, b):
    ak, bk = set(a), set(b)
    new = sorted(bk - ak)
    deleted = sorted(ak - bk)
    changed = sorted(k for k in (ak & bk) if a[k] != b[k])
    return new, changed, deleted

def main():
    tmp = tempfile.mkdtemp(prefix="difftree_")
    base = os.path.join(tmp, "base")
    os.makedirs(base)
    with tarfile.open(BASE_FULL_TAR, "r:gz") as t:
        t.extractall(base)
    base_ref = os.path.join(base, FULL_NAME)
    print("base top dir exists:", os.path.isdir(base_ref))

    m_base = walk(base_ref)
    m_rxres = walk(RXRES_TREE)
    m_rxrec = walk(RXREC_TREE)

    print("file counts: base=%d rxres=%d rxrec=%d" % (len(m_base), len(m_rxres), len(m_rxrec)))

    for label, a, b in [("rxres-vs-base(host-audit additions)", m_base, m_rxres),
                        ("rxrec-vs-base(full delta)", m_base, m_rxrec),
                        ("rxrec-vs-rxres(rxrecovery1 delta)", m_rxres, m_rxrec)]:
        new, changed, deleted = diff(a, b)
        print("\n=== %s ===" % label)
        print("  new=%d changed=%d deleted=%d" % (len(new), len(changed), len(deleted)))
        for r in new:
            print("    new    : %s" % r)
        for r in changed:
            print("    changed: %s" % r)
        for r in deleted:
            print("    deleted: %s" % r)

    shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
