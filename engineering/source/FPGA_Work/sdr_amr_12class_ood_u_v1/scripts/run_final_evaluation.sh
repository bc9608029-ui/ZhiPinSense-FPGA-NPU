#!/usr/bin/env bash
# M16: offline 12-vs-24 final evaluation + model recommendation (model-side only).
# Usage: scripts/run_final_evaluation.sh <final_checkpoint_manifest.json> \
#          [--twelve-class-config C] [--twelve-class-checkpoint CKPT]
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <final_checkpoint_manifest.json> [--twelve-class-config C] [--twelve-class-checkpoint CKPT]" >&2
  exit 2
fi
MANIFEST="$1"; shift

if [ ! -f "$MANIFEST" ]; then
  echo "missing manifest: $MANIFEST" >&2
  exit 1
fi

# Resolve + SHA-verify the exact checkpoint from the frozen manifest.
CKPT="$("$PYTHON" scripts/_resolve_checkpoint.py "$MANIFEST")"

"$PYTHON" -m scripts.run_final_evaluation --config configs/rml24_base.yaml \
  --checkpoint "$CKPT" "$@"

echo "RML24_FINAL_EVALUATION_OK"
