#!/usr/bin/env bash
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

python -c "from scripts.release_guard_v1_2 import assert_marker; print('preflight_hash=', assert_marker())"
echo "[pilot] 3 data distributions x 30 epochs, OOD-aware selection, then two-seed confirmation"
python -u -m scripts.run_ad_amr_v1_2_pilot
