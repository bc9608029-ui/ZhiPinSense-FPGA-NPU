"""Content-bound CUDA preflight marker for V1.2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from training.utils import PROJECT_ROOT

MARKER = PROJECT_ROOT / "outputs/ad_amr_v1_2/preflight/V1_2_PREFLIGHT_DONE.json"


def release_input_hash() -> str:
    digest = hashlib.sha256()
    roots = (
        "channel", "datasets", "models", "training", "evaluation", "scripts",
        "tests", "configs", "autodl_ad_amr_v1_2",
    )
    files: list[Path] = []
    for name in roots:
        root = PROJECT_ROOT / name
        files.extend(path for path in root.rglob("*") if path.is_file()
                     and path.suffix in {".py", ".yaml", ".yml", ".sh"})
    files.extend((PROJECT_ROOT / "init").glob("*.pt"))
    files.extend(PROJECT_ROOT / name for name in ("requirements.txt", "pretraining_readiness.json"))
    for path in sorted(files, key=lambda value: value.as_posix()):
        digest.update(path.relative_to(PROJECT_ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def write_marker(payload: dict[str, object]) -> str:
    value = release_input_hash()
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(json.dumps({"release_input_hash": value, "payload": payload}, indent=2), encoding="utf-8")
    return value


def assert_marker() -> str:
    if not MARKER.exists():
        raise RuntimeError("V1.2 CUDA preflight marker is missing")
    stored = json.loads(MARKER.read_text(encoding="utf-8"))["release_input_hash"]
    current = release_input_hash()
    if stored != current:
        raise RuntimeError(f"V1.2 release inputs changed after preflight: {stored} != {current}")
    return current
