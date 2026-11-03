#!/usr/bin/env python3
"""Stage the AutoDL package and emit SHA256SUMS.txt + PROVENANCE_SHA256.txt.

Deterministic: fixed traversal order, excludes caches/outputs, and writes the
V1-verbatim provenance manifest so copied V1 sources can be byte-checked.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {"__pycache__", "outputs", "dist", ".git", ".diag", ".pytest_cache"}
EXCLUDE_SUFFIXES = (".pyc", ".pyo")

# Files that are NEW or MODIFIED in V2 (everything else is verbatim V1).
V2_NEW_OR_MODIFIED = {
    "v2",
    "docs",
    "tools",
    "configs/v2_base.yaml",
    "configs/search_space_v2.yaml",
    "scripts/capture_real_rf_12class.sh",
    "scripts/preflight.py",
    "scripts/data_audit.py",
    "scripts/baseline_reproduce.py",
    "scripts/setup_env.sh",
    "scripts/run_preflight.sh",
    "scripts/run_data_audit.sh",
    "scripts/run_leakage_check.sh",
    "scripts/run_baseline_reproduce.sh",
    "scripts/run_pilot.sh",
    "scripts/run_select.sh",
    "scripts/run_formal.sh",
    "scripts/run_export_onnx.sh",
    "scripts/run_fake_int8.sh",
    "scripts/run_all.sh",
    "scripts/package_v2.py",
    "scripts/package_v2.sh",
    "requirements.txt",
    "README.md",
}


def _is_v2(path: Path) -> bool:
    rel = path.as_posix()
    if any(part in V2_NEW_OR_MODIFIED for part in path.parts[1:]):
        return True
    if path.is_dir() and rel in V2_NEW_OR_MODIFIED:
        return True
    if rel in V2_NEW_OR_MODIFIED:
        return True
    if path.parts and path.parts[0] in V2_NEW_OR_MODIFIED:
        return True
    return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix in EXCLUDE_SUFFIXES:
            continue
        yield path


def main() -> int:
    stage = _ROOT.parent / "dist" / "v2_stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    files = list(iter_files(_ROOT))
    rel_files = sorted(p.relative_to(_ROOT).as_posix() for p in files)

    sums_lines: list[str] = []
    provenance_lines: list[str] = [
        "# PROVENANCE_SHA256.txt — V1 verbatim copied sources (byte-check against F:\\嵌赛\\model_ad_amr_v1_2).",
        "# Format: <sha256>  <relative path>  <source>",
    ]
    v1_count = 0
    v2_count = 0
    for rel in rel_files:
        src = _ROOT / rel
        digest = _sha256(src)
        sums_lines.append(f"{digest}  {rel}")
        if _is_v2(Path(rel)):
            v2_count += 1
        else:
            v1_count += 1
            provenance_lines.append(f"{digest}  {rel}  V1-verbatim")

    # Copy files into the staging dir, then write the manifests inside it.
    for rel in rel_files:
        dst = stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_ROOT / rel, dst)

    # Write manifests with explicit LF (never CRLF) so `sha256sum -c` works on the board.
    with (stage / "SHA256SUMS.txt").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(sums_lines) + "\n")
    with (stage / "PROVENANCE_SHA256.txt").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(provenance_lines) + "\n")

    print(f"staged {len(rel_files)} files -> {stage}")
    print(f"  V1-verbatim: {v1_count}  V2 new/modified: {v2_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
