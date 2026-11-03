"""M20 test categories 14, 18, 19: Python-C++ consistency + -O2/-Werror build +
ASan/UBSan.

These need a C++ compiler (native g++ or WSL g++).  When neither is available
the module is skipped with a clear reason; the build/run is executed through the
available backend so the CPU-side detector is actually exercised here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from ood.scores import compute_scores
from ood_u import contract
from ood_u.manifest import build_ood_u_manifest, write_ood_u_manifest
from scripts.m20_board_replay import _stress_logits
from scripts.m20_common import compiler_backend, to_wsl_path

_PROJECT = Path(__file__).resolve().parents[1]
CPP_DIR = _PROJECT / "cpp"
CORE = ["ood_threshold_manifest.cpp", "ood_u_detector.cpp"]

BACKEND = compiler_backend()
pytestmark = pytest.mark.skipif(
    BACKEND is None, reason="no C++ compiler available (g++ or WSL g++)")

FLAGS_RELEASE = ["-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror"]
FLAGS_SANITIZE = ["-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                  "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]


def _exe(name: str) -> Path:
    suffix = ".exe" if (BACKEND == "native" and sys.platform == "win32") else ""
    return CPP_DIR / (name + suffix)


def _compile(sources: list[str], out_name: str, flags: list[str]) -> Path:
    exe = _exe(out_name)
    if BACKEND == "native":
        cmd = ["g++"] + flags + ["-I", str(CPP_DIR)]
        cmd += [str(CPP_DIR / s) for s in sources]
        cmd += ["-o", str(exe)]
        proc = subprocess.run(cmd, cwd=str(CPP_DIR), capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
    else:
        wdir = to_wsl_path(CPP_DIR)
        srcs = " ".join(to_wsl_path(CPP_DIR / s) for s in sources)
        out = to_wsl_path(exe)
        proc = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-lc",
             f"cd {wdir} && g++ {' '.join(flags)} -I {wdir} {srcs} -o {out}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0, f"compile failed:\n{proc.stderr}"
    return exe


def _run(exe: Path, args: list[str]) -> subprocess.CompletedProcess:
    if BACKEND == "native":
        return subprocess.run([str(exe)] + args, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
    wargs = " ".join(to_wsl_path(CPP_DIR / a) if not Path(a).is_absolute() else to_wsl_path(a)
                     for a in args)
    return subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-lc", f"{to_wsl_path(exe)} {wargs}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_cpp_detector_build_and_unit_test_release():
    # Category 19: -O2 -Wall -Wextra -Werror build; + category 6/7 semantics via
    # the C++ unit test (score values, UNKNOWN/known, NO_SIGNAL/ERROR, boundary).
    exe = _compile(CORE + ["test_ood_u_detector.cpp"], "test_ood_u_detector", FLAGS_RELEASE)
    proc = _run(exe, [])
    assert proc.returncode == 0, proc.stderr
    assert "ALL PASS" in proc.stdout


def test_cpp_detector_asan_ubsan():
    # Category 18: ASan/UBSan build + run must be clean (no leaks, no UB).
    exe = _compile(CORE + ["test_ood_u_detector.cpp"], "test_ood_u_detector_san", FLAGS_SANITIZE)
    proc = _run(exe, [])
    assert proc.returncode == 0, proc.stderr
    assert "ALL PASS" in proc.stdout


def test_python_cpp_consistency(tmp_path):
    # Category 14: the C++ detector must produce the *same* OOD score, UNKNOWN /
    # known decision, and class name as the Python reference on identical logits.
    method = "logit_margin"
    temperature = 1.0
    threshold = -0.153
    manifest = build_ood_u_manifest(
        score_method=method, temperature=temperature, threshold=threshold,
        working_points={
            "id_accept_95": {"threshold": -0.5},
            "id_accept_99": {"threshold": threshold},
            "far_ood_target": {"threshold": -15.0},
        },
        target_operating_point="id_accept_99",
        calibration_dataset_sha256="a" * 64,
        calibration_split_sha256="b" * 64,
        sample_count={"id": 1, "ood": 1},
        creation_seed=contract.OOD_SEED,
    )
    manifest_path = tmp_path / "manifest.json"
    write_ood_u_manifest(manifest, manifest_path)

    logits = _stress_logits(contract.OOD_SEED + 99, n=64)
    py_scores = compute_scores(logits, method, temperature)
    py_reject = py_scores > threshold
    py_class = [contract.UNKNOWN if py_reject[i]
                else contract.LABEL_ORDER_12[int(np.argmax(logits[i]))]
                for i in range(len(logits))]

    tsv = tmp_path / "logits.tsv"
    tsv.write_text("\n".join(" ".join(f"{v:.17g}" for v in row) for row in logits) + "\n")

    exe = _compile(CORE + ["ood_u_replay_main.cpp"], "ood_u_replay", FLAGS_RELEASE)
    proc = _run(exe, [str(manifest_path), str(tsv)])
    assert proc.returncode == 0, proc.stderr
    replay = json.loads(proc.stdout)
    decisions = replay["decisions"]
    assert len(decisions) == len(logits)

    for i, d in enumerate(decisions):
        assert abs(float(d["score"]) - float(py_scores[i])) < 1e-6, f"score mismatch at {i}"
        assert bool(d["known"]) == (not bool(py_reject[i])), f"decision mismatch at {i}"
        assert str(d["class_name"]) == py_class[i], f"class mismatch at {i}"
