#!/usr/bin/env bash
# M17: offline test suite (label order / shapes / split no-overlap / OOD direction /
# Energy stability / threshold freeze / NaN-Inf / reproducibility / contracts).
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

echo "[tests] running offline test suite"
"$PYTHON" -m pytest tests/ -q "$@"

echo "RML24_TESTS_OK"
