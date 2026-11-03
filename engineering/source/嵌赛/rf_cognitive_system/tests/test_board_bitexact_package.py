from __future__ import annotations

import subprocess
import sys


def test_board_bitexact_package_self_check() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "hardware/fpga/board_validation/compare_board_capture.py",
            "--self-test",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"status": "PASS"' in completed.stdout
    assert '"reference_rows": 19456' in completed.stdout
    assert '"final_blind_test_accessed": false' in completed.stdout
