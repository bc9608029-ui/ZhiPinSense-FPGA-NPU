#!/usr/bin/env bash
# M5 pre-training self-check: single-batch overfit probe (fails -> training is forbidden).
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

echo "[smoke] 24-class fixed-batch overfit probe"
"$PYTHON" -m scripts.overfit_probe_rml24 --config configs/rml24_smoke.yaml
echo "RML24_SMOKE_OK"
