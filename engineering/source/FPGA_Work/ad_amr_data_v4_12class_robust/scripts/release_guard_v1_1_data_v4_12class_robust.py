"""Content-bound release guard for the data-v4 robustness experiment.

PROVISIONAL — the guard is content-bound exactly like the twelve-class guard, but
covers the robustness-specific autodl directory instead of the twelve-class one.
The pilot/formal entrypoints call ``assert_robust_marker`` first, so they refuse
to start unless the robustness CUDA preflight has produced the marker for exactly
this source tree.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from training.utils import PROJECT_ROOT, load_yaml

MARKER = PROJECT_ROOT / (
    "outputs/ad_amr_v1_1_data_v4_12class_robust/preflight/ROBUST_PREFLIGHT_DONE.json"
)


def release_input_hash() -> str:
    digest = hashlib.sha256()
    roots = (
        "channel", "datasets", "models", "training", "evaluation", "scripts",
        "tests", "configs", "autodl_ad_amr_v1_1_data_v4_12class_robust",
    )
    files: list[Path] = []
    for name in roots:
        root = PROJECT_ROOT / name
        if root.exists():
            files.extend(
                path for path in root.rglob("*")
                if path.is_file() and path.suffix in {".py", ".yaml", ".yml", ".sh", ".txt"}
            )
    files.extend((PROJECT_ROOT / "init").glob("*.pt"))
    files.append(PROJECT_ROOT / "requirements.txt")
    for path in sorted(files, key=lambda value: value.as_posix()):
        digest.update(path.relative_to(PROJECT_ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def write_robust_marker(config: dict[str, Any], payload: dict[str, object]) -> str:
    value = release_input_hash()
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(json.dumps({
        "release_input_hash": value,
        "class_contract": config["signal"]["modulations"],
        "robust_status": config["robust"]["status"],
        "payload": payload,
    }, indent=2), encoding="utf-8")
    return value


def assert_robust_marker() -> str:
    if not MARKER.is_file():
        raise RuntimeError("data-v4 robustness preflight marker is missing")
    stored = json.loads(MARKER.read_text(encoding="utf-8"))
    current = release_input_hash()
    if stored.get("release_input_hash") != current:
        raise RuntimeError("data-v4 robustness release inputs changed after preflight")
    config = load_yaml("configs/ad_amr_v1_1_data_v4_12class_robust.yaml")
    if stored.get("class_contract") != config["signal"]["modulations"]:
        raise RuntimeError("twelve-class contract changed after robustness preflight")
    return current


__all__ = [
    "MARKER", "release_input_hash", "write_robust_marker", "assert_robust_marker",
]
