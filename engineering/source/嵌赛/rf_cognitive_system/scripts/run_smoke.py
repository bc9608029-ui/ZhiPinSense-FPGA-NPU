"""Run the complete bounded PC smoke workflow using the active interpreter."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(*arguments: str) -> None:
    command = [sys.executable, *arguments]
    print("\n>", " ".join(command), flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    run("-m", "pytest", "-q")
    run("-m", "evaluation.dataset_audit", "--config", "configs/baseline.yaml")
    run("generate_dataset.py", "--config", "configs/synthetic.yaml", "--save-count", "8")
    run("-m", "scripts.golden_demo")
    run("train.py", "--config", "configs/smoke.yaml")
    run("-m", "evaluation.evaluate", "--config", "configs/smoke.yaml")
    run("-m", "evaluation.snr_sweep", "--config", "configs/smoke.yaml")


if __name__ == "__main__":
    main()
