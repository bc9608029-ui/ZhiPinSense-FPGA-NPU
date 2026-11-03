import os, hashlib, sys

def h(p):
    hh = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            hh.update(c)
    return hh.hexdigest()

def tree(root):
    root = root.rstrip('/\\')
    out = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in ('__pycache__', 'bin', 'dist', '.git', 'build_gate7', 'build_gate9', 'build_gate9_rml23'))
        for n in fn:
            p = os.path.join(dp, n)
            rel = os.path.relpath(p, root).replace(os.sep, '/')
            out[rel] = h(p)
    return out

base = r"F:/嵌赛/fix10prep2_work/sdr_rml23_live_board_package_iq_rf_loopback_fix10prep2"
work = r"F:/嵌赛/fix10clean2b_work/sdr_rml23_live_board_package_iq_rf_loopback_fix10clean2b"
B = tree(base); W = tree(work)
new = sorted(set(W) - set(B))
gone = sorted(set(B) - set(W))
diff = sorted(r for r in set(W) & set(B) if W[r] != B[r])
print("NEW:", len(new))
for r in new: print("  +", r)
print("GONE:", len(gone))
for r in gone: print("  -", r)
print("MODIFIED:", len(diff))
for r in diff: print("  ~", r)
