#!/usr/bin/env bash
# run_select.sh — select top pilot candidates for formal (validation-only).
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -m v2.select "$@" 2>&1
