"""AutoDL packaging contract: LF manifests, real digests, valid shell scripts."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.package_qam_aware_v3_3_autodl import _assert_lf, _write_lf

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_write_lf_produces_lf_only_and_no_bom(tmp_path: Path) -> None:
    path = tmp_path / "manifest.txt"
    _write_lf(path, "alpha\nbeta\n")
    data = path.read_bytes()
    assert b"\r" not in data, "LF-only text must contain no carriage returns"
    assert not data.startswith(b"\xef\xbb\xbf"), "LF-only text must carry no UTF-8 BOM"
    assert data.endswith(b"\n")


def test_assert_lf_rejects_crlf(tmp_path: Path) -> None:
    path = tmp_path / "script.sh"
    path.write_bytes(b"#!/usr/bin/env bash\r\necho hi\r\n")
    with pytest.raises(RuntimeError):
        _assert_lf(path)


def test_manifest_digests_match_every_file(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    nested = tmp_path / "sub" / "b.bin"
    nested.parent.mkdir()
    nested.write_bytes(b"\x00\x01\x02\xff")

    files = sorted(path for path in tmp_path.rglob("*") if path.is_file())
    lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.relative_to(tmp_path).as_posix()}")
    manifest = tmp_path / "sha256_manifest.txt"
    _write_lf(manifest, "\n".join(lines) + "\n")

    # Exactly the format ``sha256sum -c`` accepts: "<digest>  <relative path>".
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        assert hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest() == digest
    assert len(manifest.read_text(encoding="utf-8").splitlines()) == len(files)


def test_shell_scripts_pass_bash_syntax() -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not available on this platform")
    scripts = sorted((PROJECT_ROOT / "autodl_v3_3").glob("*.sh"))
    assert scripts, "expected AutoDL shell scripts in autodl_v3_3/"
    for script in scripts:
        result = subprocess.run([bash, "-n", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, f"{script.name} failed bash -n:\n{result.stderr}"
