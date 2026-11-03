#!/usr/bin/env bash
# M16: offline 12-vs-24 final evaluation + model recommendation (model-side only).
# Usage: scripts/run_final_evaluation.sh <checkpoint.pt>
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <checkpoint.pt> [--twelve-class-config C] [--twelve-class-checkpoint CKPT]" >&2
  exit 2
fi
CKPT="$1"; shift

"$PYTHON" -m scripts.run_final_evaluation --config configs/rml24_base.yaml \
  --checkpoint "$CKPT" "$@"

echo "RML24_FINAL_EVALUATION_OK"
