#!/usr/bin/env bash
# M20 NPU logits capture: host reference bundle + capture contract (board runs the tool).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
exec python -m scripts.m20_npu_logits_capture "$@"
