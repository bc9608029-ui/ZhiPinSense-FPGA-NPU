#!/usr/bin/env bash
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

python -u -m scripts.run_ad_amr_v4_12class_robust_formal
