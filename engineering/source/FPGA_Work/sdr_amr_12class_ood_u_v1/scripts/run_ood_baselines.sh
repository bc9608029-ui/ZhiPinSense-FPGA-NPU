#!/usr/bin/env bash
# M11/M12: semantic OOD baselines (MSP / Entropy / MaxLogit / Energy) for the frozen checkpoint.
# Usage: scripts/run_ood_baselines.sh <final_checkpoint_manifest.json> [--include-12class]
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <final_checkpoint_manifest.json> [--include-12class]" >&2
  exit 2
fi
MANIFEST="$1"; shift

if [ ! -f "$MANIFEST" ]; then
  echo "missing manifest: $MANIFEST" >&2
  exit 1
fi

# Resolve + SHA-verify the exact checkpoint from the frozen manifest.
CKPT="$("$PYTHON" scripts/_resolve_checkpoint.py "$MANIFEST")"

"$PYTHON" -m scripts.run_ood_baselines --config configs/rml24_base.yaml \
  --checkpoint "$CKPT" "$@"

echo "RML24_OOD_BASELINES_OK"
