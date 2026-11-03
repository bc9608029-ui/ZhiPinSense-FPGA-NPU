#!/usr/bin/env bash
# run_24class_oe_seed2026.sh — M25-B OE verify run (frozen first seed 2026).
# Fail-closed: exits before any training unless the 24-class baseline is frozen.
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
    echo "M25B_OE_SEED2026 result=24CLASS_BASELINE_NOT_FROZEN"
    exit 0
fi

# Real training entrypoint goes here (offline pre-research does not run it).
echo "M25B_OE_SEED2026 result=READY"
