#!/usr/bin/env bash
# M13/M14: Outlier Exposure + Energy training, gated by the 1+2 seed strategy.
# Seed 2026 runs first and is compared against the frozen baseline (ID accuracy
# and Energy OOD); the remaining seeds (2027, 2028) run only on OE_DECISION
# result=PROMOTE.  See docs/OE_PROMOTION_CONTRACT.md.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

OE_CONFIG="configs/oe_energy.yaml"
BASELINE_MANIFEST="runs/rml24_base/formal/final_checkpoint_manifest.json"
BASELINE_OOD="runs/ood_baselines/ood_baselines.json"

if [ ! -f "$BASELINE_MANIFEST" ]; then
  echo "missing $BASELINE_MANIFEST; run formal training first" >&2
  exit 1
fi
if [ ! -f "$BASELINE_OOD" ]; then
  echo "missing $BASELINE_OOD; run OOD baselines first" >&2
  exit 1
fi

echo "[oe] gated OE+Energy seed strategy (verify seed 2026 -> promote 2027/2028)"
"$PYTHON" -m training.oe_decision --oe-config "$OE_CONFIG" \
  --baseline-manifest "$BASELINE_MANIFEST" --baseline-ood "$BASELINE_OOD"

echo "RML24_OE_ENERGY_OK"
