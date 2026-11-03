"""Create a clean, self-verifying V1.1 AutoDL source archive."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from training.utils import PROJECT_ROOT

EXCLUDED_PARTS = {"outputs", "dist", "__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".onnx"}


def included_files() -> list[Path]:
    result = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PROJECT_ROOT)
        if relative.as_posix() == "sha256_manifest.txt" or path.name.endswith(".zip.sha256"):
            continue
        if any(part in EXCLUDED_PARTS or part.startswith(".pytest_tmp") for part in relative.parts):
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        result.append(path)
    return sorted(result, key=lambda value: value.relative_to(PROJECT_ROOT).as_posix())


def package(destination: Path | None = None) -> tuple[Path, str, int]:
    destination = destination or PROJECT_ROOT / "dist/ad_amr_v1_1_autodl.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = included_files()
    manifest_lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_lines.append(f"{digest}  {path.relative_to(PROJECT_ROOT).as_posix()}")
    manifest = ("\n".join(manifest_lines) + "\n").encode()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(PROJECT_ROOT).as_posix())
        archive.writestr("sha256_manifest.txt", manifest)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix + ".sha256").write_text(
        f"{digest}  {destination.name}\n", encoding="ascii"
    )
    return destination, digest, len(files)


if __name__ == "__main__":
    path, digest, count = package()
    print(f"path={path}")
    print(f"sha256={digest}")
    print(f"files={count}")
