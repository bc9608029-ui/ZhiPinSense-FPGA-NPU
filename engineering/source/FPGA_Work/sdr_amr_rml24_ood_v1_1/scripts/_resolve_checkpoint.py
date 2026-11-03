"""Resolve the frozen final checkpoint from ``final_checkpoint_manifest.json``.

Prints the checkpoint path after verifying its SHA-256 equals the manifest's
``checkpoint_sha256`` (fail-closed).  Used by the downstream shell wrappers so
every step reads the same frozen manifest and re-verifies the checkpoint identity
instead of guessing a path.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_checkpoint(manifest_path: str | Path) -> str:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    checkpoint_path = manifest.get("checkpoint_path")
    expected = manifest.get("checkpoint_sha256")
    if not checkpoint_path or not expected:
        raise RuntimeError("manifest missing checkpoint_path/checkpoint_sha256")
    path = Path(checkpoint_path)
    if not path.is_file():
        raise RuntimeError(f"checkpoint missing: {path}")
    actual = _sha256(path)
    if actual != str(expected):
        raise RuntimeError(f"checkpoint SHA {actual} != manifest {expected}")
    return str(path)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: _resolve_checkpoint.py <final_checkpoint_manifest.json>", file=sys.stderr)
        return 2
    try:
        print(resolve_checkpoint(sys.argv[1]))
    except (RuntimeError, OSError) as exc:
        print(f"checkpoint resolve failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
