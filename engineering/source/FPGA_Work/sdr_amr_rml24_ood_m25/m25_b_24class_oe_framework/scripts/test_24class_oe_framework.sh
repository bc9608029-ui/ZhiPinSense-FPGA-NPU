#!/usr/bin/env bash
# test_24class_oe_framework.sh — run the M25-B unit + mock-model test suite.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== pytest =="
python -m pytest tests/ -q

echo "== compileall =="
python -m compileall -q contracts datasets audit ood training npu_boundary

echo "== baseline-gate (must print NOT_FROZEN and exit 0) =="
bash scripts/run_24class_oe_seed2026.sh
bash scripts/run_24class_oe_calibration.sh
bash scripts/run_24class_oe_final_blind.sh

echo "M25B_TEST_FRAMEWORK result=OK"
