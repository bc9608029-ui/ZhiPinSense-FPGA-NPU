"""Create a source-only twelve-class AutoDL archive (never embeds RadioML)."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from scripts.package_ad_amr_v1_1_data_v2_autodl import included_files
from training.utils import PROJECT_ROOT


def package(destination: Path | None = None) -> tuple[Path, str, int]:
    destination = destination or PROJECT_ROOT / "dist/ad_amr_v1_1_data_v3_12class_autodl.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    files = included_files()
    manifest = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
        f"{path.relative_to(PROJECT_ROOT).as_posix()}\n" for path in files
    ).encode("utf-8")
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(PROJECT_ROOT).as_posix())
        archive.writestr("sha256_manifest.txt", manifest)
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")
        names = archive.namelist()
        if any(name.endswith((".h5", ".hdf5", ".npz")) for name in names):
            raise RuntimeError("source archive unexpectedly contains public data")
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
