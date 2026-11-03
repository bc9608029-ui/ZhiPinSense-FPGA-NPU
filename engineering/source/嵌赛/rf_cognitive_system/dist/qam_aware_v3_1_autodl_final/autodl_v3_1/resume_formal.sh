#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
CHECKPOINT="${1:-outputs/qam_aware_v3_1/formal/checkpoints/last.pt}"
test -f "$CHECKPOINT"
mkdir -p outputs/qam_aware_v3_1/formal/logs
python -m training.train_qam_aware_v3_1 \
  --config configs/qam_aware_v3_1.yaml \
  --resume "$CHECKPOINT" \
  2>&1 | tee -a outputs/qam_aware_v3_1/formal/logs/autodl_console.log
python -m evaluation.evaluate_qam_aware_v3_1 --config configs/qam_aware_v3_1.yaml
python -m scripts.export_qam_aware_v3_1_onnx --config configs/qam_aware_v3_1.yaml
python -m evaluation.check_qam_aware_v3_1_acceptance
echo "V3_1_AUTODL_FORMAL_RESUME_PASS"
