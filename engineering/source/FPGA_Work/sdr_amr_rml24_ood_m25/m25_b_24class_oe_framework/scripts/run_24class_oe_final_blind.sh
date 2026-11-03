#!/usr/bin/env bash
# run_24class_oe_final_blind.sh — M25-B final blind OOD evaluation (ood_final_test).
# Fail-closed: requires the frozen baseline AND a locked threshold manifest.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
MANIFEST="${BASELINE_MANIFEST:-$ROOT/artifacts/baseline_manifest.json}"
THRESHOLD_MANIFEST="${THRESHOLD_MANIFEST:-$ROOT/artifacts/threshold_manifest.json}"

STATUS="$(python - "$MANIFEST" <<'PY'
import sys
from training.m25b_baseline_gate import baseline_status
print(baseline_status(sys.argv[1])[0])
PY
)"

if [ "$STATUS" != "24CLASS_BASELINE_FROZEN" ]; then
    echo "M25B_OE_FINAL_BLIND result=24CLASS_BASELINE_NOT_FROZEN"
    exit 0
fi

python - "$THRESHOLD_MANIFEST" <<'PY'
import json
import os
import sys
p = sys.argv[1]
if not os.path.exists(p):
    print("24CLASS_OE_RESULT result=INSUFFICIENT reason=no_threshold_manifest")
    raise SystemExit(0)
with open(p, "r", encoding="utf-8") as fh:
    manifest = json.load(fh)
if not manifest:
    print("24CLASS_OE_RESULT result=INSUFFICIENT reason=empty_threshold_manifest")
    raise SystemExit(0)
print("M25B_OE_FINAL_BLIND result=READY")
PY
