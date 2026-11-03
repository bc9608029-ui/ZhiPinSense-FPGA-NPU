#!/usr/bin/env bash
# CUDA preflight gate: the 24-class pipeline may only start training after this
# prints exactly one "CUDA_PREFLIGHT_RESULT result=PASS" line.  Any sub-check
# failure exits non-zero and prints result=FAIL.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"
CONFIG="${CONFIG:-configs/rml24_base.yaml}"

# Deterministic CUDA kernels (cudnn benchmark off; workspace fixed) so the
# preflight matrix is reproducible on the training machine.
export CUBLAS_WORKSPACE_CONFIG="${CUBLAS_WORKSPACE_CONFIG:-:4096:8}"
export PYTHONUNBUFFERED=1

echo "[preflight] CUDA preflight for RML24-OOD V1.1 (config=$CONFIG)"
"$PYTHON" -m scripts.cuda_preflight --config "$CONFIG"
