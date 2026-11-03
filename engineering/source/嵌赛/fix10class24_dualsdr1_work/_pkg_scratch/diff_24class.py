#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compute the change set of the 24-class tree relative to the fix10prep3
smoke-closeout full baseline.  Read-only analysis."""
import hashlib, os, sys, tarfile, tempfile, shutil

BASELINE_TAR = r"F:\嵌赛\fix10prep3_work\sdr_rml23_live_board_package_pc_tx_board_rx_fix10prep3\dist\sdr_rml23_fix10prep3_smoke_closeout_boardtest_full.tar.gz"
TREE24 = r"F:\嵌赛\fix10class24_dualsdr1_work\sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24"

EXCLUDED_DIRS = {"host_tests/bin", "host_tests/__pycache__", "host_tools/__pycache__",
                 "scripts/__pycache__", "dist", ".git", "host_tools/.build_burst_cache",
                 "results"}
EXCLUDED_FILES = {"host_tests/build_host_tests.log", "host_tests/run_tests.log"}

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()

def walk(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = sorted(d for d in dns
                        if os.path.relpath(os.path.join(dp, d), root).replace(os.sep, "/") not in EXCLUDED_DIRS)
        for n in fns:
            rel = os.path.relpath(os.path.join(dp, n), root).replace(os.sep, "/")
            if rel in EXCLUDED_FILES:
                continue
            out[rel] = sha(os.path.join(dp, n))
    return out

def main():
    with tempfile.TemporaryDirectory(prefix="diff24_") as td:
        with tarfile.open(BASELINE_TAR, "r:gz") as t:
            t.extractall(td, filter="data")
        top = os.path.join(td, "sdr_rml23_live_board_package_pc_tx_board_rx_fix10prep3")
        base = walk(top)
        tree = walk(TREE24)
    base_keys = set(base); tree_keys = set(tree)
    new = sorted(tree_keys - base_keys)
    deleted = sorted(base_keys - tree_keys)
    changed = sorted(k for k in (tree_keys & base_keys) if tree[k] != base[k])
    identical = sorted(k for k in (tree_keys & base_keys) if tree[k] == base[k])
    print("== new in 24class tree ==")
    for k in new: print("  +", k)
    print("== deleted (in baseline only) ==")
    for k in deleted: print("  -", k)
    print("== changed ==")
    for k in changed: print("  ~", k)
    print("== counts ==")
    print("base=%d tree=%d new=%d deleted=%d changed=%d identical=%d"
          % (len(base), len(tree), len(new), len(deleted), len(changed), len(identical)))

if __name__ == "__main__":
    main()
