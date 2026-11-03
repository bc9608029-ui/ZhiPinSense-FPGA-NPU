#!/usr/bin/env bash
# run_24class_oe_extra_seeds.sh — M25-B OE extra seeds (2027, 2028), gated on PROMOTE.
# Fail-closed: requires the frozen baseline and the seed2026 PROMOTE decision.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
MANIFEST="${BASELINE_MANIFEST:-$ROOT/artifacts/baseline_manifest.json}"
DECISION_JSON="${OE_DECISION_JSON:-$ROOT/artifacts/oe_pilot_seed2026_report.json}"

STATUS="$(python - "$MANIFEST" <<'PY'
import sys
from training.m25b_baseline_gate import baseline_status
print(baseline_status(sys.argv[1])[0])
PY
)"

if [ "$STATUS" != "24CLASS_BASELINE_FROZEN" ]; then
    echo "M25B_OE_EXTRA_SEEDS result=24CLASS_BASELINE_NOT_FROZEN"
    exit 0
fi

DECISION="$(python - "$DECISION_JSON" <<'PY'
import json
import os
import sys
p = sys.argv[1]
if not os.path.exists(p):
    print("MISSING")
else:
    with open(p, "r", encoding="utf-8") as fh:
        print(json.load(fh).get("decision", "MISSING"))
PY
)"

if [ "$DECISION" != "PROMOTE" ]; then
    echo "M25B_OE_EXTRA_SEEDS result=REJECT reason=not_promoted"
    exit 0
fi

# Real training entrypoint goes here (offline pre-research does not run it).
echo "M25B_OE_EXTRA_SEEDS result=READY"
