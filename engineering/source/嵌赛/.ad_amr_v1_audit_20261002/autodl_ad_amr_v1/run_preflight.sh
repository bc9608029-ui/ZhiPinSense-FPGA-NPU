#!/usr/bin/env bash
# AD-AMR V1 — CUDA preflight (functional smoke only, NOT a performance gate).
#
# Steps:
#   [1] host pytest suite (CPU cases run; the CUDA smoke is exercised next);
#   [2] P0 + P1 2-epoch AMP smoke on GPU with finiteness assertions;
#   [3] checkpoint save/load/resume round-trip on GPU;
#   [4] evaluation + ONNX export + ORT parity.
# Prints AD_AMR_V1_CUDA_PREFLIGHT_PASS only when every step succeeds.
set -euo pipefail

export CUBLAS_WORKSPACE_CONFIG=:4096:8

echo "[preflight] step 1/4 — pytest suite"
python -m pytest tests -q

echo "[preflight] step 2-4/4 — P0+P1 GPU smoke, resume, eval, ONNX"
python -m scripts.run_cuda_preflight
