"""Package the AD-AMR V1 source tree into a self-contained AutoDL archive.

The archive carries every file needed to re-run CPU tests / smoke and to run the
AutoDL CUDA preflight + staged pilot on a fresh GPU host: source, configs, tests,
AutoDL scripts, the frozen V2 checkpoint (reference only), requirements, README,
and a ``sha256_manifest.txt`` (LF-only, no BOM).  ``outputs/``, ``dist/``,
``__pycache__``, ``*.pyc`` and other residue are excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "ad_amr_v1_autodl.zip"

INCLUDE_DIRS = [
    "configs", "models", "datasets", "channel", "training", "evaluation",
    "scripts", "tests", "autodl_ad_amr_v1", "docs", "init",
]
INCLUDE_FILES = ["requirements.txt", "README.md"]

EXCLUDE_SUFFIXES = (".pyc",)
EXCLUDE_DIR_NAMES = {"__pycache__", "outputs", "dist", "input", ".git"}
EXCLUDE_FILE_NAMES = {"_paper_text.txt", "pretraining_readiness.json", "access_audit.json"}


def _iter_payload() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE_DIRS:
        directory = PROJECT_ROOT / name
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(PROJECT_ROOT)
            if any(part in EXCLUDE_DIR_NAMES for part in rel.parts):
                continue
            if path.suffix in EXCLUDE_SUFFIXES or path.name in EXCLUDE_FILE_NAMES:
                continue
            files.append(path)
    for name in INCLUDE_FILES:
        path = PROJECT_ROOT / name
        if path.exists():
            files.append(path)
    return files


def build_manifest(files: list[Path]) -> list[str]:
    lines = []
    for path in files:
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        size = path.stat().st_size
        lines.append(f"{digest}  {size}  {rel}")
    return lines


def package(archive_path: Path | None = None) -> dict[str, object]:
    files = _iter_payload()
    manifest_lines = build_manifest(files)

    dist_dir = PROJECT_ROOT / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    archive = archive_path or (dist_dir / ARCHIVE_NAME)

    manifest_rel = "sha256_manifest.txt"
    manifest_bytes = ("\n".join(manifest_lines) + "\n").encode("utf-8")

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            zf.write(path, rel)
        zf.writestr(manifest_rel, manifest_bytes)

    # Verification.
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        bad_crc = zf.testzip()
        manifest_text = zf.read(manifest_rel).decode("utf-8")
        has_bom = manifest_text.startswith("﻿")
        has_crlf = "\r\n" in manifest_text
        digest_mismatches = 0
        for line in manifest_text.splitlines():
            if not line.strip():
                continue
            digest, size_str, rel = line.split("  ")
            if rel not in names:
                digest_mismatches += 1
                continue
            actual = hashlib.sha256(zf.read(rel)).hexdigest()
            if actual != digest:
                digest_mismatches += 1

        residue = [n for n in names if any(p in EXCLUDE_DIR_NAMES for p in n.split("/"))
                   or n.endswith(".pyc")]

    archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    return {
        "archive": archive.as_posix(),
        "sha256": archive_digest,
        "size_bytes": archive.stat().st_size,
        "manifest_entries": len(manifest_lines),
        "manifest_lf_only": not has_crlf,
        "manifest_no_bom": not has_bom,
        "manifest_digest_mismatches": digest_mismatches,
        "zip_crc_ok": bad_crc is None,
        "residue": residue,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    result = package(Path(args.output) if args.output else None)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
