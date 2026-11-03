#!/usr/bin/env bash
# M20 score benchmark: five OOD-U methods on ood_validation.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
exec python -m scripts.m20_score_benchmark "$@"
