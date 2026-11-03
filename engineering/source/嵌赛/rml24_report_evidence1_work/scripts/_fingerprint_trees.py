#!/usr/bin/env python3
"""Compute a read-only source-tree fingerprint (sorted "relpath\\tsize" manifest, SHA-256).

Used to prove the 9 existing RML24 source trees are unchanged before/after the
read-only evidence-ledger build.  Fingerprint = SHA-256 over the sorted manifest of
(relative_path, file_size) lines; it detects add/remove/rename/resize, not in-place
same-size content edits (a documented limitation).
"""
import hashlib
import os
import sys

ROOT = r"F:\嵌赛"

TREES = [
    "fix10prep_work",
    "fix10prep2_work",
    "fix10prep3_work",
    "fix10class24_prep1_work",
    "fix10class24_dualsdr1_work",
    "fix10class24_dualsdr2_work",
    "fix10class24_rxresidual_audit1_work",
    "fix10class24_prospective_validation_prep1_work",
    "constellation_ui_desktop1_work",
]


def fingerprint(tree_abs):
    lines = []
    for root, _dirs, files in os.walk(tree_abs):
        for fn in files:
            p = os.path.join(root, fn)
            try:
                sz = os.path.getsize(p)
            except OSError:
                sz = -1
            rel = os.path.relpath(p, tree_abs).replace(os.sep, "/")
            lines.append(rel + "\t" + str(sz))
    lines.sort()
    data = ("\n".join(lines) + "\n").encode("utf-8")
    return len(lines), hashlib.sha256(data).hexdigest()


def main():
    out = []
    for t in TREES:
        tree_abs = os.path.join(ROOT, t)
        if not os.path.isdir(tree_abs):
            out.append((t, "SOURCE_NOT_PRESENT", "0", "SOURCE_NOT_PRESENT"))
            continue
        n, h = fingerprint(tree_abs)
        out.append((t, "PRESENT", str(n), h))
    for t, status, n, h in out:
        sys.stdout.write("\t".join([t, status, n, h]) + "\n")


if __name__ == "__main__":
    main()
