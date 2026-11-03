"""V1.1 reliability — downstream steps resolve the frozen checkpoint by manifest.

``scripts/_resolve_checkpoint.py`` verifies the checkpoint SHA-256 against the
frozen manifest before printing the path; the OOD-baseline / export / final-eval
shell wrappers use it so no step guesses a checkpoint path.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from scripts._resolve_checkpoint import resolve_checkpoint


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_resolve_checkpoint_returns_verified_path(tmp_path):
    data = b"checkpoint-bytes"
    ckpt = tmp_path / "best.pt"
    ckpt.write_bytes(data)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "checkpoint_path": str(ckpt), "checkpoint_sha256": _sha256(data),
    }), encoding="utf-8")
    assert resolve_checkpoint(manifest) == str(ckpt)


def test_resolve_checkpoint_sha_mismatch_fails_closed(tmp_path):
    ckpt = tmp_path / "best.pt"
    ckpt.write_bytes(b"real-bytes")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "checkpoint_path": str(ckpt), "checkpoint_sha256": "0" * 64,
    }), encoding="utf-8")
    with pytest.raises(RuntimeError, match="SHA"):
        resolve_checkpoint(manifest)


def test_resolve_checkpoint_missing_file_fails_closed(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "checkpoint_path": str(tmp_path / "absent.pt"), "checkpoint_sha256": "0" * 64,
    }), encoding="utf-8")
    with pytest.raises(RuntimeError, match="missing"):
        resolve_checkpoint(manifest)


def test_resolve_checkpoint_missing_fields_fails_closed(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"checkpoint_path": "x"}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="missing checkpoint_path"):
        resolve_checkpoint(manifest)
