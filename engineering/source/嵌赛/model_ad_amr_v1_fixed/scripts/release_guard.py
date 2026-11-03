"""Content-hash binding between CUDA preflight and the performance pilot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER_PATH = ROOT / "outputs/ad_amr_v1/preflight/PREFLIGHT_DONE.json"
INCLUDE_DIRS = (
    "models", "datasets", "channel", "training", "evaluation", "scripts", "tests",
    "configs", "autodl_ad_amr_v1",
)


def release_files() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE_DIRS:
        directory = ROOT / name
        for path in directory.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files.append(path)
    files.extend([ROOT / "requirements.txt", ROOT / "init/v2_time_power_phase_best.pt"])
    return sorted(set(files), key=lambda p: p.relative_to(ROOT).as_posix())


def release_input_hash() -> str:
    digest = hashlib.sha256()
    for path in release_files():
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def write_preflight_marker(result: dict) -> str:
    value = release_input_hash()
    MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"status": "passed", "release_input_hash": value, "result": result}
    MARKER_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")
    return value


def assert_preflight_marker() -> str:
    if not MARKER_PATH.exists():
        raise RuntimeError("CUDA preflight marker is missing; run run_preflight.sh first.")
    payload = json.loads(MARKER_PATH.read_text(encoding="utf-8"))
    expected = release_input_hash()
    actual = payload.get("release_input_hash")
    if payload.get("status") != "passed" or actual != expected:
        raise RuntimeError(
            "CUDA preflight marker is stale for the current source/config/checkpoint hash: "
            f"marker={actual}, current={expected}"
        )
    return expected

