#!/usr/bin/env bash
# M20 final blind test: single access on ood_final_test at the frozen threshold.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
exec python -m scripts.m20_final_blind_test "$@"
