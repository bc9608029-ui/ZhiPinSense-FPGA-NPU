#!/usr/bin/env bash
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

python -c "from scripts.release_guard_v1_1_data_v2 import assert_marker; print('preflight_hash=', assert_marker())"
python -u -m scripts.run_ad_amr_v1_1_data_v2_pilot

