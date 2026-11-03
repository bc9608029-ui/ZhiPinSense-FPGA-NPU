#!/usr/bin/env bash
# data-v4 鲁棒性 pilot（fail closed）。
# 先校验 preflight 标记（确认源码树自 preflight 后未变），再跑 baseline vs A/B/C 候选选择。
# 只有唯一候选达标才写 selected_candidate.json；否则 NO_GO 退出。
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -c "from scripts.release_guard_v1_1_data_v4_12class_robust import assert_robust_marker; print('preflight_hash=', assert_robust_marker())"
python -u -m scripts.run_ad_amr_v4_12class_robust_pilot
