#!/usr/bin/env bash
# run_fake_int8.sh — fake symmetric INT8 weight-quantization accuracy check.
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -m v2.fake_int8 "$@" 2>&1
