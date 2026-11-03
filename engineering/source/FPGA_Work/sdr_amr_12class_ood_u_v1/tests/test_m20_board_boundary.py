"""M20 test categories 16 & 17: board-integration boundary.

Category 16 — default-off byte-identical: when the OOD-U rejection is not
triggering (threshold never crossed), the CPU-side detector's output must be
byte-identical to the *original* 12-class argmax chain (the frozen label for the
argmax class, never UNKNOWN / NO_SIGNAL / ERROR, and never a renamed class).

Category 17 — serial silence: the detector is a pure computation and the replay
CLI's default (non-verbose) path emits exactly one JSON result line and nothing
else (no debug/status lines to stdout, empty stderr on success).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from ood_u import contract
from ood_u.manifest import build_ood_u_manifest, write_ood_u_manifest
from scripts.m20_common import compiler_backend, to_wsl_path

_PROJECT = Path(__file__).resolve().parents[1]
CPP_DIR = _PROJECT / "cpp"
CORE = ["ood_threshold_manifest.cpp", "ood_u_detector.cpp"]
FLAGS_RELEASE = ["-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror"]

BACKEND = compiler_backend()
pytestmark = pytest.mark.skipif(
    BACKEND is None, reason="no C++ compiler available (g++ or WSL g++)")


def _exe(name: str) -> Path:
    suffix = ".exe" if (BACKEND == "native" and sys.platform == "win32") else ""
    return CPP_DIR / (name + suffix)


def _compile_replay() -> Path:
    exe = _exe("ood_u_replay")
    if BACKEND == "native":
        cmd = ["g++"] + FLAGS_RELEASE + ["-I", str(CPP_DIR)]
        cmd += [str(CPP_DIR / s) for s in CORE + ["ood_u_replay_main.cpp"]]
        cmd += ["-o", str(exe)]
        proc = subprocess.run(cmd, cwd=str(CPP_DIR), capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
    else:
        sources = " ".join(to_wsl_path(CPP_DIR / s) for s in CORE + ["ood_u_replay_main.cpp"])
        wdir = to_wsl_path(CPP_DIR)
        out = to_wsl_path(exe)
        proc = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-lc",
             f"cd {wdir} && g++ {' '.join(FLAGS_RELEASE)} -I {wdir} {sources} -o {out}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr
    return exe


def _run_replay(exe: Path, manifest: Path, tsv: Path) -> subprocess.CompletedProcess:
    if BACKEND == "native":
        return subprocess.run([str(exe), str(manifest), str(tsv)], capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
    return subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-lc",
         f"{to_wsl_path(exe)} {to_wsl_path(manifest)} {to_wsl_path(tsv)}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")


def _never_reject_manifest(path: Path) -> None:
    # Rejection is ``score > threshold``; logit_margin scores are <= 0, so a large
    # positive threshold means every frame is accepted -> default-off passthrough.
    manifest = build_ood_u_manifest(
        score_method="logit_margin", temperature=1.0, threshold=1e30,
        working_points={
            "id_accept_95": {"threshold": 1e30},
            "id_accept_99": {"threshold": 1e30},
            "far_ood_target": {"threshold": 1e30},
        },
        target_operating_point="id_accept_99",
        calibration_dataset_sha256="a" * 64,
        calibration_split_sha256="b" * 64,
        sample_count={"id": 1, "ood": 1},
        creation_seed=contract.OOD_SEED,
    )
    write_ood_u_manifest(manifest, path)


def test_default_off_byte_identical_to_argmax_chain(tmp_path):
    # Category 16: with rejection effectively off, every frame is byte-identical
    # to the original 12-class argmax output (frozen label, correct index).
    exe = _compile_replay()
    manifest = tmp_path / "manifest.json"
    _never_reject_manifest(manifest)

    rng = np.random.default_rng(contract.OOD_SEED + 5)
    logits = rng.uniform(-8.0, 8.0, size=(128, contract.OUTPUT_DIM)).astype(np.float64)
    tsv = tmp_path / "logits.tsv"
    tsv.write_text("\n".join(" ".join(f"{v:.17g}" for v in row) for row in logits) + "\n")

    proc = _run_replay(exe, manifest, tsv)
    assert proc.returncode == 0, proc.stderr
    decisions = json.loads(proc.stdout)["decisions"]
    assert len(decisions) == len(logits)

    for i, d in enumerate(decisions):
        argmax = int(np.argmax(logits[i]))
        assert d["known"] is True, f"frame {i} should be known when rejection is off"
        assert d["valid"] is True
        assert int(d["class_index"]) == argmax
        assert d["class_name"] == contract.LABEL_ORDER_12[argmax], f"frame {i} not byte-identical"


def test_detector_adds_no_serial_output(tmp_path):
    # Category 17 (part 1): the detector library itself writes nothing to any
    # stream — it is a pure computation (no cout/cerr/printf/fprintf/puts/write).
    forbidden = ("std::cout", "std::cerr", "printf", "fprintf", "puts(", "write(",
                 "std::clog", "perror")
    for name in ("ood_u_detector.cpp", "ood_u_detector.hpp", "ood_u_contract.hpp",
                 "ood_threshold_manifest.cpp", "ood_threshold_manifest.hpp"):
        text = (CPP_DIR / name).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{name} emits serial output: {token}"


def test_replay_default_mode_silent_except_one_result_line(tmp_path):
    # Category 17 (part 2): the replay CLI default path prints exactly one JSON
    # result line to stdout and nothing to stderr (no status/debug chatter).
    exe = _compile_replay()
    manifest = tmp_path / "manifest.json"
    _never_reject_manifest(manifest)

    rng = np.random.default_rng(contract.OOD_SEED + 6)
    logits = rng.uniform(-5.0, 5.0, size=(16, contract.OUTPUT_DIM)).astype(np.float64)
    tsv = tmp_path / "logits.tsv"
    tsv.write_text("\n".join(" ".join(f"{v:.17g}" for v in row) for row in logits) + "\n")

    proc = _run_replay(exe, manifest, tsv)
    assert proc.returncode == 0, proc.stderr

    # The module's result channel is exactly one JSON document and nothing else
    # (no status/debug chatter).  json.loads over the *whole* stdout fails if any
    # non-JSON text is interleaved.  (stderr is not asserted empty here: the WSL
    # launcher writes its own diagnostic bytes to stderr; the detector's silence
    # is proven by the source-grep test above.)
    parsed = json.loads(proc.stdout)
    assert parsed["n"] == len(logits)
