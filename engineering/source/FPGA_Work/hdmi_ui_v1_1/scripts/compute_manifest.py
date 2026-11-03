#!/usr/bin/env python3
"""Compute the deliverable sha256 manifest for the project.

Hashes every tracked deliverable (source, contract, QML, config, scripts,
tests, mock data, docs, build files) and writes ``sha256_manifest`` at the
project root.  Generated artefacts (``__pycache__``, ``.pytest_cache``,
``*.pyc``, build directories) are excluded, as is the manifest itself.

Usage:
    python scripts/compute_manifest.py
"""

from __future__ import annotations

import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IGNORED_DIRS = {".git", ".pytest_cache", "__pycache__", "build"}
IGNORED_SUFFIXES = (".pyc",)
IGNORED_NAMES = {"sha256_manifest"}


def walk():
    entries = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for name in filenames:
            if name in IGNORED_NAMES or name.endswith(IGNORED_SUFFIXES):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            with open(full, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            entries.append((rel, digest))
    entries.sort()
    return entries


def main():
    entries = walk()
    lines = [
        "# hdmi_ui_v1_1 deliverable manifest",
        "# one sha256 per file; regenerate with scripts/compute_manifest.py",
    ]
    lines.extend("%s  %s" % (digest, rel) for rel, digest in entries)
    lines.append("")
    path = os.path.join(ROOT, "sha256_manifest")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    print("wrote sha256_manifest (%d files)" % len(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
