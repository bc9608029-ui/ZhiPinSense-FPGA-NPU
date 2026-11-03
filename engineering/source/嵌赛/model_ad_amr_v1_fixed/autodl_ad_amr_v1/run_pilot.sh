#!/usr/bin/env bash
# Staged performance pilot. No test/final-blind split is instantiated.
set -euo pipefail

export CUBLAS_WORKSPACE_CONFIG=:4096:8

python -c "from scripts.release_guard import assert_preflight_marker; print('preflight_hash=', assert_preflight_marker())"
echo "[pilot] Stage A P0/P1; Stage B two seeds; paired V2 validation/OOD gates"
python -m scripts.run_pilot
