#!/usr/bin/env bash
# M20 logits parity: PyTorch fp32 vs ONNX fp32 (and optional NPU int8).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
exec python -m scripts.m20_logits_parity "$@"
