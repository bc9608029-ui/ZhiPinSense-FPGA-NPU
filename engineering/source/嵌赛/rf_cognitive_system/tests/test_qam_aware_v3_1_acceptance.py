"""Fail-closed behaviour of the V3.1 promotion-gate script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evaluation.check_qam_aware_v3_1_acceptance import check_acceptance

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLASSES = ["BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM"]


def _write_failing_report(report_path: Path, snr_path: Path) -> None:
    report = {
        "suites": {
            "v2_compatible": {
                "accuracy": 0.0,
                "macro_f1": 0.0,
                "qam_mean_accuracy": 0.0,
                "per_class_accuracy": {name: 0.0 for name in CLASSES},
            }
        }
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")
    snr_path.write_text("snr_db,accuracy,macro_f1,samples\n0,0.0,0.0,4000\n10,0.0,0.0,4000\n20,0.0,0.0,4000\n", encoding="utf-8")


def test_acceptance_fails_closed_below_gates(tmp_path: Path) -> None:
    report = tmp_path / "evaluation.json"
    snr = tmp_path / "snr.csv"
    _write_failing_report(report, snr)
    result = check_acceptance(
        str(report), str(snr), gate_path="configs/qam_aware_v3_1_acceptance.yaml"
    )
    assert result["passed"] is False
    assert all(value is False for value in result["checks"].values())


def test_acceptance_raises_when_v2_suite_missing(tmp_path: Path) -> None:
    report = tmp_path / "evaluation.json"
    report.write_text(json.dumps({"suites": {"v3_1_robust": {}}}), encoding="utf-8")
    snr = tmp_path / "snr.csv"
    snr.write_text("snr_db,accuracy\n", encoding="utf-8")
    with pytest.raises(KeyError):
        check_acceptance(str(report), str(snr))


def test_acceptance_script_exits_nonzero_on_failed_gate(tmp_path: Path) -> None:
    report = tmp_path / "evaluation.json"
    snr = tmp_path / "snr.csv"
    _write_failing_report(report, snr)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "evaluation.check_qam_aware_v3_1_acceptance",
            "--report",
            str(report),
            "--snr",
            str(snr),
            "--gates",
            "configs/qam_aware_v3_1_acceptance.yaml",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, result.stderr
