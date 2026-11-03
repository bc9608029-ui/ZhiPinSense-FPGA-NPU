#!/usr/bin/env bash
# M15: export the 24-class model to ONNX (opset 17, operator-whitelist + ORT parity gates).
# Usage: scripts/run_export.sh <checkpoint.pt>
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <checkpoint.pt>" >&2
  exit 2
fi
CKPT="$1"; shift

"$PYTHON" -m scripts.export_rml24_onnx --config configs/rml24_base.yaml --checkpoint "$CKPT"

echo "RML24_EXPORT_OK"
