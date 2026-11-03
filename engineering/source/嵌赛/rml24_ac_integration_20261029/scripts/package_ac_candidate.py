#!/usr/bin/env python3
"""Package the AC-integration candidate into a deterministic, self-verifying archive.

Run from the tree root (the dir that contains ``overlay/``, ``scripts/``, ``docs/``,
``tests/``)::

    python3 -I scripts/package_ac_candidate.py

Outputs:
  * ``SHA256SUMS_AC.txt``  -- authoritative ``sha256  relpath`` manifest of every
    shipped file (overlay + scripts + docs + tests; ``__pycache__`` and the
    offline ``local_base/`` test scaffolding are EXCLUDED).
  * ``dist/rml24_ac_integration_candidate.tar.gz`` -- deterministic gzip tar
    (sorted entries, fixed mtime/uid/gid) containing the manifest + all files.

The archive is what gets uploaded to the board.  ``scripts/verify_ac_package.py``
independently unpacks it into a clean dir and re-checks every SHA plus the
flat-deploy import closure and both start entries.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import sys
import tarfile
from pathlib import Path

TREE = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "SHA256SUMS_AC.txt"
ARCHIVE_NAME = "rml24_ac_integration_candidate.tar.gz"

# Top-level dirs that ship in the delivery.  Everything else at the tree root is
# offline scaffolding (local_base/, runtime/, results/, dist/, pytest cache).
SHIP_DIRS = ("overlay", "scripts", "docs", "tests")

# Root-level handoff doc (authoritative for this round; supersedes the A-line
# HANDOFF_SCAN_GAP_UI_FIX1.md / NEXT_AGENT_HANDOFF_UI2.md, which are NOT shipped).
ROOT_FILES = ("HANDOFF_AC_INTEGRATION.md",)


def iter_ship_files() -> list[Path]:
    files: list[Path] = []
    for rel in ROOT_FILES:
        p = TREE / rel
        if not p.is_file():
            raise SystemExit(f"PACKAGE missing required file: {p}")
        files.append(p)
    for d in SHIP_DIRS:
        root = TREE / d
        if not root.is_dir():
            raise SystemExit(f"PACKAGE missing required dir: {root}")
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            if "__pycache__" in p.parts:
                continue
            files.append(p)
    return files


def manifest_lines(files: list[Path]) -> str:
    rows = []
    for p in files:
        rel = p.relative_to(TREE).as_posix()
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        rows.append(f"{digest}  {rel}")
    return "\n".join(sorted(rows)) + "\n"


def _tarinfo_for(p: Path, rel: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(rel)
    data = p.read_bytes()
    info.size = len(data)
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mode = 0o644
    return info, data


def main() -> int:
    files = iter_ship_files()
    manifest_text = manifest_lines(files)

    (TREE / MANIFEST_NAME).write_text(manifest_text, encoding="utf-8")

    dist = TREE / "dist"
    dist.mkdir(exist_ok=True)
    archive = dist / ARCHIVE_NAME

    # Build the tar fully in memory (deterministic: sorted entries, fixed meta).
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tf:
        # Manifest first.
        manifest_rel = MANIFEST_NAME
        info, data = _tarinfo_for(TREE / MANIFEST_NAME, manifest_rel)
        tf.addfile(info, io.BytesIO(data))
        for p in files:
            rel = p.relative_to(TREE).as_posix()
            info, data = _tarinfo_for(p, rel)
            tf.addfile(info, io.BytesIO(data))
    payload = raw.getvalue()

    gz = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=gz, mtime=0) as f:
        f.write(payload)
    archive.write_bytes(gz.getvalue())

    archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    # RECEIPT lives OUTSIDE the archive (dist/ is not shipped) so it never
    # self-references; the archive itself is self-verifying via SHA256SUMS_AC.txt.
    (dist / "RECEIPT_AC.txt").write_text(
        f"archive={ARCHIVE_NAME}\narchive_sha256={archive_sha}\nfiles={len(files)}\n"
        f"manifest={MANIFEST_NAME}\n",
        encoding="utf-8",
    )
    print(f"PACKAGE manifest={MANIFEST_NAME} files={len(files)}")
    print(f"PACKAGE archive={archive}")
    print(f"PACKAGE archive_sha256={archive_sha}")
    print(f"PACKAGE result=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
