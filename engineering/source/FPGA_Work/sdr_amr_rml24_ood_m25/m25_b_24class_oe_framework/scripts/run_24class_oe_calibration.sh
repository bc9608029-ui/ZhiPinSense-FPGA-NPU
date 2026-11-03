#!/usr/bin/env bash
# run_24class_oe_calibration.sh — M25-B OOD threshold calibration (validation only).
# Fail-closed: requires the frozen baseline before calibrating anything.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
MANIFEST="${BASELINE_MANIFEST:-$ROOT/artifacts/baseline_manifest.json}"

STATUS="$(python - "$MANIFEST" <<'PY'
import sys
from training.m25b_baseline_gate import baseline_status
print(baseline_status(sys.argv[1])[0])
PY
)"

if [ "$STATUS" != "24CLASS_BASELINE_FROZEN" ]; then
    echo "M25B_OE_CALIBRATION result=24CLASS_BASELINE_NOT_FROZEN"
    exit 0
fi

# Real calibration entrypoint goes here (locks thresholds on ood_validation only).
echo "M25B_OE_CALIBRATION result=READY"
