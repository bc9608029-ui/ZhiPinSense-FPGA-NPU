#!/usr/bin/env python3
"""_diff_ui_snapshots.py -- byte-level diff of before/after UI snapshot PPMs.

Reports, per page, how many RGB bytes (and what fraction of the 1280x720 frame)
changed between the pre-redesign (artifacts/ui_before) and post-redesign
(artifacts/ui_after) renders.  This is the quantitative half of deliverable 3/4:
the visual proof that the redesign changed every page (and how much).
"""
import os
import sys

W, H = 1280, 720
FRAME = W * H * 3


def pixel_offset(data):
    i = 2
    toks = 0
    while toks < 3:
        while data[i] in b" \t\r\n":
            i += 1
        if data[i:i + 1] == b"#":
            while data[i] != 0x0A:
                i += 1
            continue
        j = i
        while data[j] not in b" \t\r\n":
            j += 1
        toks += 1
        i = j
    while data[i] in b" \t\r\n":
        i += 1
    return i


def main():
    before = sys.argv[1] if len(sys.argv) > 1 else "artifacts/ui_before"
    after = sys.argv[2] if len(sys.argv) > 2 else "artifacts/ui_after"
    names = sorted(n for n in os.listdir(before) if n.endswith(".ppm"))
    after_ppm = set(n for n in os.listdir(after) if n.endswith(".ppm"))
    print(f"before_ppm={len(names)} after_ppm={len(after_ppm)}")
    total = 0
    rows = []
    for n in names:
        if n not in after_ppm:
            print(f"  MISSING after: {n}")
            continue
        b = open(os.path.join(before, n), "rb").read()
        a = open(os.path.join(after, n), "rb").read()
        pb = b[pixel_offset(b):]
        pa = a[pixel_offset(a):]
        assert len(pb) == len(pa) == FRAME, (n, len(pb), len(pa))
        diff = sum(1 for x, y in zip(pb, pa) if x != y)
        total += diff
        rows.append((n, diff))
    rows.sort(key=lambda r: -r[1])
    for n, diff in rows:
        print(f"  {n:24s} diff={diff:8d} bytes ({diff / FRAME * 100:.2f}%)")
    print(f"TOTAL diff bytes={total}  mean_per_page={total / max(1, len(rows)):.1f}")
    if total == 0:
        print("WARNING: before == after byte-for-byte (redesign changed nothing?)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
