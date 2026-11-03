#!/usr/bin/env bash
# run_24class_oe_decision.sh — M25-B OE promotion decision (fail-closed toward REJECT).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
BASELINE_OOD="${1:-$ROOT/artifacts/baseline_ood.json}"
OE_OOD="${2:-$ROOT/artifacts/oe_ood_seed2026.json}"

python - "$BASELINE_OOD" "$OE_OOD" <<'PY'
import json
import os
import sys
from training.m25b_oe_controls import decide_oe_promotion, id_metrics_from_result, energy_far_metrics

paths = sys.argv[1], sys.argv[2]
if any(not os.path.exists(p) for p in paths):
    # Fail-closed: without real reports, never fabricate a PROMOTE.
    print("OE_DECISION result=REJECT reason=missing_inputs")
    raise SystemExit(0)

with open(paths[0], "r", encoding="utf-8") as fh:
    baseline_ood = json.load(fh)
with open(paths[1], "r", encoding="utf-8") as fh:
    oe_ood = json.load(fh)

# ID metrics ride along inside the OOD reports for this offline harness.
baseline_id = id_metrics_from_result(baseline_ood.get("id_result", {}))
oe_id = id_metrics_from_result(oe_ood.get("id_result", {}))
d = decide_oe_promotion(baseline_id, oe_id,
                        energy_far_metrics(baseline_ood),
                        energy_far_metrics(oe_ood))
print(f"OE_DECISION result={d['decision']} reasons={d['reasons']}")
PY
