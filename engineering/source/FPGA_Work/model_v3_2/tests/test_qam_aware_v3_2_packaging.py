"""LF-only manifests and shell scripts (no BOM, no CRLF) for Linux sha256sum -c."""

from __future__ import annotations

import pytest

from scripts.package_qam_aware_v3_2_autodl import _assert_lf, _write_lf
from scripts.package_qam_aware_v3_2_results import sha256
from training.qam_aware_v3_2_utils import write_text_lf
from training.utils import PROJECT_ROOT


def test_write_lf_is_lf_only_no_bom(tmp_path) -> None:
    path = tmp_path / "manifest.txt"
    _write_lf(path, "line one\nline two\n")
    raw = path.read_bytes()
    assert b"\r" not in raw
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert raw.endswith(b"\n")
    _assert_lf(path)


def test_assert_lf_rejects_crlf(tmp_path) -> None:
    path = tmp_path / "bad.sh"
    path.write_bytes(b"#!/usr/bin/env bash\r\nset -e\r\n")
    with pytest.raises(RuntimeError):
        _assert_lf(path)


def test_write_text_lf_is_lf_only_no_bom(tmp_path) -> None:
    path = write_text_lf(tmp_path / "nested" / "a.txt", "a\nb\n")
    raw = path.read_bytes()
    assert b"\r" not in raw
    assert not raw.startswith(b"\xef\xbb\xbf")


def test_all_shell_scripts_are_lf_only() -> None:
    for script in sorted((PROJECT_ROOT / "autodl_v3_2").glob("*.sh")):
        raw = script.read_bytes()
        assert b"\r" not in raw, f"{script.name} contains CRLF"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{script.name} starts with a BOM"


def test_sha256_matches_manifest_line(tmp_path) -> None:
    payload = b"portable formal results\n"
    subject = tmp_path / "results.bin"
    subject.write_bytes(payload)
    digest = sha256(subject)
    line = f"{digest}  {subject.name}"
    assert line.split("  ", 1)[0] == digest
    assert line.split("  ", 1)[1] == subject.name
