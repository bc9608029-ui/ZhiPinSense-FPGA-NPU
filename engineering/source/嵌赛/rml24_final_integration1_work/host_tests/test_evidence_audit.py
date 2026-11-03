from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "amr_rescue_gmsk_candidate_20261026"
MODEL = ROOT.parent / "fix10class24_full24_accuracy1_work" / "sdr_rml24_fix10class24_full24_accuracy1" / "model_rml24_bf16"


class EvidenceAuditTests(unittest.TestCase):
    def test_evidence_audit_passes(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            report = Path(directory) / "audit.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "audit_frozen_evidence.py"),
                    "--source-root",
                    str(SOURCE),
                    "--integration-root",
                    str(ROOT),
                    "--model-dir",
                    str(MODEL),
                    "--out",
                    str(report),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            value = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(value["status"], "PASS")
            self.assertEqual(value["validation_combined"], {"baseline": 403, "candidate": 463, "total": 480})
            self.assertEqual(value["raw_capture_replay"], "PENDING_CAPTURE_COPY")


if __name__ == "__main__":
    unittest.main()

