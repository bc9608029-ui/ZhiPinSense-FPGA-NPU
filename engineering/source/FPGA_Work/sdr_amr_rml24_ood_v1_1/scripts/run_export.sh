#!/usr/bin/env bash
# M15: export the 24-class model to ONNX (opset 17, operator-whitelist + ORT parity gates).
# Usage: scripts/run_export.sh <final_checkpoint_manifest.json>
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <final_checkpoint_manifest.json>" >&2
  exit 2
fi
MANIFEST="$1"; shift

if [ ! -f "$MANIFEST" ]; then
  echo "missing manifest: $MANIFEST" >&2
  exit 1
fi

# Resolve + SHA-verify the exact checkpoint from the frozen manifest.
CKPT="$("$PYTHON" scripts/_resolve_checkpoint.py "$MANIFEST")"

"$PYTHON" -m scripts.export_rml24_onnx --config configs/rml24_base.yaml \
  --checkpoint "$CKPT" --manifest "$MANIFEST"

echo "RML24_EXPORT_OK"
