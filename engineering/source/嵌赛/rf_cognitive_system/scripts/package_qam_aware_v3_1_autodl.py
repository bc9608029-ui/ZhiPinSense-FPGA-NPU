"""Create a self-contained, English-named AutoDL source archive for V3.1."""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "dist" / "qam_aware_v3_1_autodl_final"
ARCHIVE = ROOT / "dist" / "qam_aware_v3_1_autodl_final.zip"

DIRECTORIES = (
    "autodl_v3_1",
    "channel",
    "configs",
    "datasets",
    "deployment",
    "evaluation",
    "models",
    "scripts",
    "tests",
    "training",
)
ROOT_FILES = ("pyproject.toml", "requirements_autodl_v3.txt", "train.py")
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_NAMES = {"__pycache__", ".pytest_cache", ".pytest_tmp", "outputs", "dist"}


def _copy_tree(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if any(part in EXCLUDED_NAMES for part in relative.parts):
            continue
        if path.is_dir() or path.suffix in EXCLUDED_SUFFIXES:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def main() -> None:
    if DESTINATION.exists():
        shutil.rmtree(DESTINATION)
    DESTINATION.mkdir(parents=True)
    for directory in DIRECTORIES:
        _copy_tree(ROOT / directory, DESTINATION / directory)
    for filename in ROOT_FILES:
        shutil.copy2(ROOT / filename, DESTINATION / filename)

    files = sorted(path for path in DESTINATION.rglob("*") if path.is_file())
    manifest_lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_lines.append(f"{digest}  {path.relative_to(DESTINATION).as_posix()}")
    (DESTINATION / "sha256_manifest.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as handle:
        for path in sorted(DESTINATION.rglob("*")):
            if path.is_file():
                handle.write(path, Path(DESTINATION.name) / path.relative_to(DESTINATION))
    print(f"package={DESTINATION}")
    print(f"archive={ARCHIVE}")
    print(f"files={len(files) + 1}")
    print(f"archive_sha256={hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
