"""Create a self-contained, English-named AutoDL source archive for V3.2.

Unlike V3.1, this package also ships ``init/`` (the frozen V2 champion
checkpoint) because it is the backbone-initialization source and the
distillation teacher.
"""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "dist" / "qam_aware_v3_2_autodl"
ARCHIVE = ROOT / "dist" / "qam_aware_v3_2_autodl.zip"

DIRECTORIES = (
    "autodl_v3_2",
    "channel",
    "configs",
    "datasets",
    "deployment",
    "docs",
    "dsp",
    "evaluation",
    "init",
    "models",
    "scripts",
    "tests",
    "training",
    "visualization",
)
ROOT_FILES = ("pyproject.toml", "requirements_autodl_v3.txt", "train.py", "generate_dataset.py")
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_NAMES = {"__pycache__", ".pytest_cache", ".pytest_tmp", "outputs", "dist", "input"}


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
        source = ROOT / directory
        if source.exists():
            _copy_tree(source, DESTINATION / directory)
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
