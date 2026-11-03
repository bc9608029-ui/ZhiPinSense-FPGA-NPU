"""Create a self-contained, English-named AutoDL source archive for V3.3.

Ships ``init/`` (the frozen V2 champion checkpoint) because it is the
backbone-initialization source, and ``hardware/`` (the FPGA Mandatory-Core
reference) for the numeric-domain consistency and bit-exact tests.  The archive
is deterministic: every file is recorded in an LF-only ``sha256_manifest.txt``
so ``sha256sum -c`` works under Linux.
"""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "dist" / "qam_aware_v3_3_autodl"
ARCHIVE = ROOT / "dist" / "qam_aware_v3_3_autodl.zip"

DIRECTORIES = (
    "autodl_v3_3",
    "channel",
    "configs",
    "datasets",
    "deployment",
    "docs",
    "dsp",
    "evaluation",
    "hardware",
    "init",
    "models",
    "scripts",
    "tests",
    "training",
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


def _write_lf(path: Path, text: str) -> None:
    # Force LF (no CRLF, no BOM) so ``sha256sum -c`` works under Linux semantics.
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _assert_lf(path: Path) -> None:
    if b"\r" in path.read_bytes():
        raise RuntimeError(
            f"{path.name} contains CRLF bytes; shell scripts and manifests must be LF-only"
        )


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
    for path in files:
        if path.suffix == ".sh":
            _assert_lf(path)
    manifest_lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_lines.append(f"{digest}  {path.relative_to(DESTINATION).as_posix()}")
    _write_lf(DESTINATION / "sha256_manifest.txt", "\n".join(manifest_lines) + "\n")
    _assert_lf(DESTINATION / "sha256_manifest.txt")

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
