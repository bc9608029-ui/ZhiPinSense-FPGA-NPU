#!/usr/bin/env bash
# run_export_onnx.sh — export the V2 candidate to opset-17 ONNX (operator gated).
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -m v2.export_onnx "$@" 2>&1
