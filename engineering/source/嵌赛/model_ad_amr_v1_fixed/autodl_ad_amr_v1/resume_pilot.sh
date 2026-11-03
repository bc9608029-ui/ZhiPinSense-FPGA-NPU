#!/usr/bin/env bash
# Resume completed/partial pilot runs from their strict last.pt checkpoints.
set -euo pipefail

export CUBLAS_WORKSPACE_CONFIG=:4096:8

python -c "from scripts.release_guard import assert_preflight_marker; print('preflight_hash=', assert_preflight_marker())"
echo "[resume_pilot] resuming staged pilot"
python -m scripts.run_pilot
