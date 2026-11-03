#!/usr/bin/env bash
# data-v4 鲁棒性 formal（fail closed）。
# 正式入口脚本本身会校验：FINAL_CONFIG_APPROVED 标记存在 + final_config_approved=true +
# 当前源码树哈希与锁定标记一致 + config SHA 一致。任一不满足即拒绝启动。
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -u -m scripts.run_ad_amr_v4_12class_robust_formal
