"""Capture reproducible Python and package information for Baseline V1."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from training.utils import PROJECT_ROOT, environment_info


def main() -> None:
    destination = PROJECT_ROOT / "environment"
    destination.mkdir(parents=True, exist_ok=True)
    frozen = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
    (destination / "baseline_v1_requirements_lock.txt").write_text(frozen, encoding="utf-8")
    details = environment_info()
    details["executable"] = sys.executable
    details["pip_freeze_file"] = "environment/baseline_v1_requirements_lock.txt"
    (destination / "baseline_v1_environment.json").write_text(json.dumps(details, indent=2), encoding="utf-8")
    print(json.dumps(details, indent=2))


if __name__ == "__main__":
    main()
