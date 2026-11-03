#!/usr/bin/env bash
# Release-blocking CUDA preflight. This is functional validation, not formal training.
set -euo pipefail

export CUBLAS_WORKSPACE_CONFIG=:4096:8

echo "[preflight] step 1/2 - full source test suite"
python -m pytest tests -q

echo "[preflight] step 2/2 - production CUDA train/resume/eval/export for P0 and P1"
python -m scripts.run_cuda_preflight
