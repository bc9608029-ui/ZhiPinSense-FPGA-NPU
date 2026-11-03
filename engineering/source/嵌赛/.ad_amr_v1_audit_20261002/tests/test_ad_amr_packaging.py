"""Packaging tests: bash -n on AutoDL scripts + ZIP/manifest/LF verification."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.package_ad_amr_autodl import package

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _bash_available() -> bool:
    return shutil.which("bash") is not None


@pytest.mark.skipif(not _bash_available(), reason="bash not available on this host")
def test_bash_syntax_all_autodl_scripts() -> None:
    scripts = sorted((PROJECT_ROOT / "autodl_ad_amr_v1").glob("*.sh"))
    assert scripts, "no AutoDL scripts found"
    for script in scripts:
        result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, f"bash -n failed for {script.name}: {result.stderr}"


def test_package_zip_manifest_lf(tmp_path) -> None:
    archive = tmp_path / "ad_amr_v1_autodl.zip"
    result = package(archive)
    assert result["zip_crc_ok"] is True
    assert result["manifest_entries"] > 0
    assert result["manifest_lf_only"] is True
    assert result["manifest_no_bom"] is True
    assert result["manifest_digest_mismatches"] == 0
    assert result["residue"] == []
    assert archive.exists()
    assert result["sha256"] and len(result["sha256"]) == 64
