#!/usr/bin/env bash
# M11/M12: semantic OOD baselines (MSP / Entropy / MaxLogit / Energy) for a trained checkpoint.
# Usage: scripts/run_ood_baselines.sh <checkpoint.pt> [--include-12class]
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <checkpoint.pt> [--include-12class]" >&2
  exit 2
fi
CKPT="$1"; shift

"$PYTHON" -m scripts.run_ood_baselines --config configs/rml24_base.yaml \
  --checkpoint "$CKPT" "$@"

echo "RML24_OOD_BASELINES_OK"
