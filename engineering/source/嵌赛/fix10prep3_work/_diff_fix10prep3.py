#!/usr/bin/env python3
import os, hashlib

base = "/mnt/f/嵌赛/fix10prep2_work/sdr_rml23_live_board_package_iq_rf_loopback_fix10prep2"
cur  = "/mnt/f/嵌赛/fix10prep3_work/sdr_rml23_live_board_package_pc_tx_board_rx_fix10prep3"

EXC = {"host_tests/bin", "scripts/__pycache__", "host_tools/__pycache__",
       "dist", ".git", "host_tools/.build_burst_cache", "results"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def walk(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(
            d for d in dn
            if os.path.relpath(os.path.join(dp, d), root).replace(os.sep, "/")
            not in EXC)
        for n in fn:
            rel = os.path.relpath(os.path.join(dp, n), root).replace(os.sep, "/")
            out[rel] = os.path.join(dp, n)
    return out


B = walk(base)
C = walk(cur)
new = sorted(set(C) - set(B))
mod = sorted(r for r in set(B) & set(C) if sha(B[r]) != sha(C[r]))
dele = sorted(set(B) - set(C))

print("NEW (%d):" % len(new))
for r in new:
    print("  " + r)
print("MODIFIED (%d):" % len(mod))
for r in mod:
    print("  " + r)
print("DELETED (%d):" % len(dele))
for r in dele:
    print("  " + r)
