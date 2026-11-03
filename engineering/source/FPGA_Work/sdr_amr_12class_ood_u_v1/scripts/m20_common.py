"""Shared helpers for the M20 one-click scripts.

Each script: (1) resolves the project root from its own location (no CWD
dependency), (2) generates a unique run id, (3) emits exactly one final result
line, and (4) fails closed on any error.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def new_run_id() -> str:
    return f"m20_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{int(time.time() * 1000) % 1_000_000:06d}"


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p.resolve()


def emit_result(result: str, run_id: str, **fields: Any) -> None:
    extras = " ".join(f"{key}={value}" for key, value in fields.items())
    line = f"M20_RESULT result={result} run_id={run_id}"
    if extras:
        line += " " + extras
    print(line)


def fail(run_id: str, reason: str) -> None:
    print(f"M20_RESULT result=FAIL run_id={run_id} reason={reason}", file=sys.stderr)
    sys.exit(1)


def write_json(path: str | Path, data: Any) -> Path:
    path = resolve_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_json(path: str | Path) -> Any:
    path = resolve_path(path)
    if not path.is_file():
        raise FileNotFoundError(f"required input missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"input is not valid JSON: {path}") from exc


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--checkpoint", default="model_12class/seed2026_best.pt",
                        help="path to the 12-class checkpoint (SHA-verified)")
    parser.add_argument("--out-dir", default=None,
                        help="output directory (defaults to a per-step runs/ directory)")


def run(parser: argparse.ArgumentParser, fn: Any) -> None:
    args = parser.parse_args()
    try:
        fn(args)
    except SystemExit:
        raise
    except Exception as exc:  # fail closed on any unexpected error
        run_id = getattr(args, "run_id", None) or "unknown"
        fail(run_id, f"{type(exc).__name__}: {exc}")


def compiler_backend() -> str | None:
    """Return ``"native"`` if ``g++`` is on PATH, ``"wsl"`` if WSL Ubuntu has g++,
    else ``None``.  Used to compile/run the CPU-side C++ detector from the host.
    """
    if shutil.which("g++"):
        return "native"
    try:
        proc = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-lc", "g++ --version"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
        if proc.returncode == 0:
            return "wsl"
    except Exception:
        pass
    return None


def to_wsl_path(path: str | Path) -> str:
    """Translate a Windows absolute path to its WSL ``/mnt/<drive>/...`` form."""
    p = Path(path).resolve()
    drive = p.drive.rstrip(":").lower()
    rest = str(p)[len(p.drive):].replace("\\", "/")
    return f"/mnt/{drive}{rest}"


def run_shell(argv: list[str], *, cwd: str | Path | None = None,
              timeout: int = 300) -> subprocess.CompletedProcess:
    """Run a command on the host (native g++) or inside WSL, returning the proc."""
    backend = compiler_backend()
    if backend == "wsl":
        argv = ["wsl", "-d", "Ubuntu", "--", "bash", "-lc", " ".join(argv)]
        cwd = None  # WSL paths are already absolute /mnt/...
    elif backend is None:
        raise RuntimeError("no C++ compiler available (g++ or WSL g++)")
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


__all__ = ["PROJECT_ROOT", "new_run_id", "resolve_path", "emit_result", "fail",
           "write_json", "read_json", "add_common_args", "run",
           "compiler_backend", "to_wsl_path", "run_shell"]
