"""Content-bound CUDA/data preflight marker for V1.1 data-v2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from datasets.radioml2018_dataset import load_audit
from training.utils import PROJECT_ROOT, resolve_project_path

MARKER = PROJECT_ROOT / "outputs/ad_amr_v1_1_data_v2/preflight/DATA_V2_PREFLIGHT_DONE.json"


def release_input_hash() -> str:
    digest = hashlib.sha256()
    roots = ("channel", "datasets", "models", "training", "evaluation", "scripts", "tests", "configs",
             "autodl_ad_amr_v1_1_data_v2")
    files: list[Path] = []
    for name in roots:
        root = PROJECT_ROOT / name
        if root.exists():
            files.extend(path for path in root.rglob("*") if path.is_file()
                         and path.suffix in {".py", ".yaml", ".yml", ".sh", ".txt"})
    files.extend((PROJECT_ROOT / "init").glob("*.pt"))
    files.append(PROJECT_ROOT / "requirements.txt")
    for path in sorted(files, key=lambda value: value.as_posix()):
        digest.update(path.relative_to(PROJECT_ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def data_identity(config: dict) -> dict[str, str]:
    audit = load_audit(config["public_data"]["audit_path"])
    return {"dataset_sha256": str(audit["sha256"]), "index_sha256": str(audit["index_sha256"])}


def write_marker(config: dict, payload: dict[str, object]) -> str:
    value = release_input_hash()
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(json.dumps({
        "release_input_hash": value, "data_identity": data_identity(config), "payload": payload,
    }, indent=2), encoding="utf-8")
    return value


def assert_marker() -> str:
    if not MARKER.is_file():
        raise RuntimeError("V1.1 data-v2 CUDA/data preflight marker is missing")
    stored = json.loads(MARKER.read_text(encoding="utf-8"))
    current = release_input_hash()
    if stored.get("release_input_hash") != current:
        raise RuntimeError("V1.1 data-v2 release inputs changed after preflight")
    from training.utils import load_yaml
    config = load_yaml("configs/ad_amr_v1_1_data_v2.yaml")
    if stored.get("data_identity") != data_identity(config):
        raise RuntimeError("RadioML dataset or split identity changed after preflight")
    return current
