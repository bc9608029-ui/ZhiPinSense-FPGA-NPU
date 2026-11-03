"""M20 board replay: Python-C++ detector consistency (Section 十二).

Builds the CPU-side C++ detector + replay CLI, feeds it the *same* raw logits
the Python reference scored (the parity IQ set's logits plus deterministic
random/offset/tie stress vectors), and asserts the OOD score, the UNKNOWN /
known decision, and the class name agree exactly between Python and C++.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

from ood.scores import compute_scores
from ood_u import contract
from ood_u.manifest import read_ood_u_manifest
from ood_u.model import load_model, predict_logits
from scripts.m20_common import (
    PROJECT_ROOT,
    add_common_args,
    compiler_backend,
    emit_result,
    fail,
    new_run_id,
    resolve_path,
    run,
    to_wsl_path,
    write_json,
)
from scripts.m20_parity_data import build_parity_iq

CPP_DIR = PROJECT_ROOT / "cpp"
_REPLAY_SRC = ["ood_threshold_manifest.cpp", "ood_u_detector.cpp", "ood_u_replay_main.cpp"]
_SCORE_TOL = 1e-6


def _exe(name: str, backend: str) -> Path:
    return CPP_DIR / (name + (".exe" if backend == "native" and sys.platform == "win32" else ""))


def _build_replay() -> tuple[str, Path]:
    """Build the replay CLI; returns (backend, exe_path)."""
    backend = compiler_backend()
    if backend is None:
        raise RuntimeError("no C++ compiler available (g++ or WSL g++)")
    exe = _exe("ood_u_replay", backend)
    flags = "-std=c++17 -O2 -Wall -Wextra -Werror"
    if backend == "native":
        cmd = ["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(CPP_DIR)]
        cmd += [str(CPP_DIR / s) for s in _REPLAY_SRC]
        cmd += ["-o", str(exe)]
        proc = subprocess.run(cmd, cwd=str(CPP_DIR), capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
    else:
        wdir = to_wsl_path(CPP_DIR)
        srcs = " ".join(to_wsl_path(CPP_DIR / s) for s in _REPLAY_SRC)
        out = to_wsl_path(exe)
        proc = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-lc",
             f"cd {wdir} && g++ {flags} -I {wdir} {srcs} -o {out}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        fail("unknown", "C++ replay build failed:\n" + proc.stderr)
    return backend, exe


def _stress_logits(seed: int, n: int = 64) -> np.ndarray:
    """Deterministic logit vectors covering ties, offsets, and magnitudes."""
    rng = np.random.default_rng(seed)
    rows: list[np.ndarray] = []
    for _ in range(n):
        kind = int(rng.integers(0, 3))
        if kind == 0:
            rows.append(rng.uniform(-5.0, 5.0, size=12))
        elif kind == 1:
            rows.append(rng.uniform(-5.0, 5.0, size=12) + 1000.0)  # large common offset
        else:
            row = rng.uniform(-5.0, 5.0, size=12)
            row[int(rng.integers(0, 12))] = row[int(rng.integers(0, 12))]  # near-tie
            rows.append(row)
    return np.stack(rows).astype(np.float64)


def main(args: argparse.Namespace) -> None:
    run_id = new_run_id()
    out_dir = resolve_path(args.out_dir or "runs/m20_board_replay")
    manifest_path = resolve_path(args.manifest or "runs/m20_threshold_calibration/ood_u_threshold_manifest.json")
    manifest = read_ood_u_manifest(manifest_path)
    model = load_model(resolve_path(args.checkpoint))

    method = manifest["score_method"]
    temperature = manifest["temperature"]
    threshold = manifest["threshold"]

    planar, labels = build_parity_iq()
    model_logits = predict_logits(model, planar)
    stress = _stress_logits(contract.OOD_SEED + 99)
    logits = np.vstack([model_logits, stress]).astype(np.float64)

    # Python reference.
    py_scores = compute_scores(logits, method, temperature)
    py_decision = py_scores > threshold
    py_class = []
    for i, score in enumerate(py_scores):
        if py_decision[i]:
            py_class.append("UNKNOWN")
        else:
            py_class.append(contract.LABEL_ORDER_12[int(np.argmax(logits[i]))])

    # Write logits.tsv for the C++ replay.
    tsv_path = out_dir / "replay_logits.tsv"
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    with tsv_path.open("w", encoding="utf-8") as handle:
        for row in logits:
            handle.write(" ".join(f"{v:.17g}" for v in row) + "\n")

    # Build + run the C++ replay tool.
    backend, exe = _build_replay()
    if backend == "native":
        proc = subprocess.run([str(exe), str(manifest_path), str(tsv_path)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
    else:
        proc = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-lc",
             f"{to_wsl_path(exe)} {to_wsl_path(manifest_path)} {to_wsl_path(tsv_path)}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        fail(run_id, "C++ replay run failed:\n" + proc.stderr)
    try:
        replay = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        fail(run_id, f"C++ replay output not valid JSON: {exc}")

    decisions = replay["decisions"]
    if len(decisions) != len(logits):
        fail(run_id, f"C++ replay returned {len(decisions)} decisions, expected {len(logits)}")

    score_diffs = []
    decision_mismatch = 0
    class_mismatch = 0
    for i, d in enumerate(decisions):
        cpp_score = float(d["score"])
        score_diffs.append(abs(cpp_score - float(py_scores[i])))
        if bool(d["known"]) == bool(py_decision[i]):
            decision_mismatch += 1
        if str(d["class_name"]) != py_class[i]:
            class_mismatch += 1

    max_score_diff = float(max(score_diffs))
    report: dict[str, Any] = {
        "run_id": run_id,
        "step": "board_replay",
        "n_samples": len(logits),
        "score_method": method,
        "temperature": temperature,
        "threshold": threshold,
        "max_score_diff": max_score_diff,
        "score_tolerance": _SCORE_TOL,
        "decision_agreement": 1.0 - decision_mismatch / len(logits),
        "class_name_agreement": 1.0 - class_mismatch / len(logits),
    }
    out_path = write_json(out_dir / "board_replay_report.json", report)

    if max_score_diff > _SCORE_TOL or decision_mismatch or class_mismatch:
        fail(run_id, f"Python-C++ inconsistency: max_score_diff={max_score_diff}, "
                     f"decision_mismatch={decision_mismatch}, class_mismatch={class_mismatch}")

    emit_result("PASS", run_id,
                n_samples=len(logits),
                max_score_diff=round(max_score_diff, 9),
                decision_agreement=report["decision_agreement"],
                class_name_agreement=report["class_name_agreement"],
                report=str(out_path.relative_to(PROJECT_ROOT)))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="M20 board replay (Python-C++ consistency)")
    add_common_args(parser)
    parser.add_argument("--manifest", default=None, help="frozen OOD-U threshold manifest")
    return parser


if __name__ == "__main__":
    run(build_parser(), main)
