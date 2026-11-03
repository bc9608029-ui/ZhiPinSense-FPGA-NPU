#!/usr/bin/env bash
# M20 threshold calibration: select method + freeze manifest (write-once).
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
exec python -m scripts.m20_threshold_calibration "$@"
