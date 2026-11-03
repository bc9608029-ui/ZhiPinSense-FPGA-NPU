"""Packaging tests: bash -n on AutoDL scripts + ZIP/manifest/LF verification."""

from __future__ import annotations

import shutil
import subprocess
import hashlib
import zipfile
from pathlib import Path

import pytest

from scripts.package_ad_amr_v1_2_autodl import package

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _bash_available() -> bool:
    return shutil.which("bash") is not None


@pytest.mark.skipif(not _bash_available(), reason="bash not available on this host")
def test_bash_syntax_all_autodl_scripts() -> None:
    scripts = sorted((PROJECT_ROOT / "autodl_ad_amr_v1_2").glob("*.sh"))
    assert scripts, "no AutoDL scripts found"
    for script in scripts:
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, f"bash -n failed for {script.name}: {result.stderr}"


def test_package_zip_manifest_lf(tmp_path) -> None:
    archive = tmp_path / "ad_amr_v1_2_autodl.zip"
    path, digest, count = package(archive)
    assert path == archive and count > 0
    assert archive.exists()
    assert len(digest) == 64
    with zipfile.ZipFile(archive) as package_zip:
        assert package_zip.testzip() is None
        names = package_zip.namelist()
        assert "sha256_manifest.txt" in names
        assert any(name.startswith("autodl_ad_amr_v1_2/") for name in names)
        assert not any(name.startswith("autodl_ad_amr_v1_1/") for name in names)
        assert not any("__pycache__" in name or name.startswith("outputs/") for name in names)
        manifest = package_zip.read("sha256_manifest.txt")
        assert b"\r" not in manifest and not manifest.startswith(b"\xef\xbb\xbf")
        for line in manifest.decode("ascii").splitlines():
            expected, name = line.split("  ", 1)
            assert hashlib.sha256(package_zip.read(name)).hexdigest() == expected
