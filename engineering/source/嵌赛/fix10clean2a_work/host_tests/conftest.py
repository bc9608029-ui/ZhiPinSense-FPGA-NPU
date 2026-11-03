"""Shared path setup for the fix10clean2a host tests.

Adds the task's scripts/ and the frozen deployment's merge-contract modules so
the four test modules can import them without a packaging step.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
MERGE_DIR = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\postprocess"
CONTRACT_DIR = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\contracts"

for _p in (str(SCRIPTS), MERGE_DIR, CONTRACT_DIR):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)
