#!/usr/bin/env bash
set -euo pipefail

# 人工审阅 pilot 结果后执行：把唯一达标候选锁定为 formal。
python -u -m scripts.lock_robust_formal_config
