#!/usr/bin/env bash
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

python -c "from scripts.release_guard_v1_1_data_v4_12class_robust import assert_robust_marker; print('preflight_hash=', assert_robust_marker())"
python -u -m scripts.run_ad_amr_v4_12class_robust_pilot
