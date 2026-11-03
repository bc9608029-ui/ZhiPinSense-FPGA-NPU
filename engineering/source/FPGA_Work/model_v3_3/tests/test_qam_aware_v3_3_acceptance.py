"""Fail-closed behaviour of the V3.3 multi-seed promotion gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evaluation.check_qam_aware_v3_3_multi_seed_acceptance import check_multi_seed_acceptance

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLASSES = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]
GATE_PATH = "configs/qam_aware_v3_3_acceptance.yaml"


def _write_seed(
    seed_dir: Path,
    *,
    accuracy: float = 0.0,
    macro_f1: float = 0.0,
    qam: float = 0.0,
    per_class: float = 0.0,
    snr: float = 0.0,
    fpga_acc_gap: float = 0.0,
    fpga_f1_gap: float = 0.0,
) -> None:
    tables = seed_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    report = {
        "checkpoint": str(seed_dir / "best.pt"),
        "suites": {
            "v2_compatible": {
                "accuracy": accuracy,
                "macro_f1": macro_f1,
                "qam_mean_accuracy": qam,
                "per_class_accuracy": {name: per_class for name in CLASSES},
            }
        },
        "fpga_sim_gap": {"accuracy_gap": fpga_acc_gap, "macro_f1_gap": fpga_f1_gap},
    }
    (tables / "evaluation.json").write_text(json.dumps(report), encoding="utf-8")
    snr_csv = "snr_db,accuracy,macro_f1,samples\n"
    snr_csv += "\n".join(f"{key},{snr},0.0,4000" for key in (0, 10, 20)) + "\n"
    (tables / "v2_compatible_snr_metrics.csv").write_text(snr_csv, encoding="utf-8")


def test_gate_fails_closed_below_bars(tmp_path: Path) -> None:
    seeds = []
    for i in range(3):
        seed_dir = tmp_path / f"seed{i}"
        _write_seed(seed_dir, accuracy=0.0, macro_f1=0.0, qam=0.0, per_class=0.0, snr=0.0)
        seeds.append(seed_dir)
    result = check_multi_seed_acceptance(seeds, GATE_PATH)
    assert result["passed"] is False
    assert result["checks"]["mean_accuracy_gain"] is False
    assert result["checks"]["mean_macro_f1_gain"] is False
    assert result["checks"]["mean_qam_mean_gain"] is False


def test_gate_passes_a_strong_candidate(tmp_path: Path) -> None:
    seeds = []
    for i in range(3):
        seed_dir = tmp_path / f"seed{i}"
        # per_class 0.95 clears every class floor (2FSK baseline 0.9076 is the
        # highest), and snr 0.95 clears the 0/10/20 dB floors (20 dB baseline 0.933).
        _write_seed(seed_dir, accuracy=0.75, macro_f1=0.75, qam=0.55, per_class=0.95, snr=0.95)
        seeds.append(seed_dir)
    result = check_multi_seed_acceptance(seeds, GATE_PATH)
    assert result["passed"] is True


def test_gate_rejects_large_fpga_sim_gap(tmp_path: Path) -> None:
    seeds = []
    for i in range(3):
        seed_dir = tmp_path / f"seed{i}"
        _write_seed(seed_dir, accuracy=0.75, macro_f1=0.75, qam=0.55, per_class=0.95,
                    snr=0.95, fpga_acc_gap=0.05, fpga_f1_gap=0.05)
        seeds.append(seed_dir)
    result = check_multi_seed_acceptance(seeds, GATE_PATH)
    assert result["passed"] is False
    assert any("fpga_sim" in key and value is False for key, value in result["checks"].items())


def test_gate_rejects_a_single_regressing_seed(tmp_path: Path) -> None:
    seeds = []
    for i in range(3):
        seed_dir = tmp_path / f"seed{i}"
        # Two strong seeds, one seed that regresses a class hard.
        if i == 2:
            _write_seed(seed_dir, accuracy=0.75, macro_f1=0.75, qam=0.55, per_class=0.3, snr=0.95)
        else:
            _write_seed(seed_dir, accuracy=0.75, macro_f1=0.75, qam=0.55, per_class=0.95, snr=0.95)
        seeds.append(seed_dir)
    result = check_multi_seed_acceptance(seeds, GATE_PATH)
    assert result["passed"] is False


def test_gate_raises_when_suite_missing(tmp_path: Path) -> None:
    seed_dir = tmp_path / "seed0"
    tables = seed_dir / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    (tables / "evaluation.json").write_text(json.dumps({"suites": {}}), encoding="utf-8")
    (tables / "v2_compatible_snr_metrics.csv").write_text("snr_db,accuracy\n", encoding="utf-8")
    with pytest.raises(KeyError):
        check_multi_seed_acceptance([seed_dir], GATE_PATH)


def test_acceptance_script_exits_nonzero_on_failed_gate(tmp_path: Path) -> None:
    seeds = []
    for i in range(3):
        seed_dir = tmp_path / f"seed{i}"
        _write_seed(seed_dir, accuracy=0.0, macro_f1=0.0, qam=0.0, per_class=0.0, snr=0.0)
        seeds.append(seed_dir)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluation.check_qam_aware_v3_3_multi_seed_acceptance",
            "--seed-dirs",
            *[str(seed) for seed in seeds],
            "--gates",
            GATE_PATH,
            "--out",
            str(tmp_path / "out.json"),
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, result.stderr
