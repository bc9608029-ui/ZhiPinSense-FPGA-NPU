#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
mkdir -p outputs/qam_aware_v3_2/formal/logs
python -m evaluation.audit_qam_aware_v3_2_dataset --config configs/qam_aware_v3_2.yaml
python -m training.train_qam_aware_v3_2 --config configs/qam_aware_v3_2.yaml \
  2>&1 | tee outputs/qam_aware_v3_2/formal/logs/autodl_console.log
python -m evaluation.evaluate_qam_aware_v3_2 --config configs/qam_aware_v3_2.yaml
python -m scripts.export_qam_aware_v3_2_onnx --config configs/qam_aware_v3_2.yaml
python -m evaluation.check_qam_aware_v3_2_acceptance
echo "V3_2_AUTODL_FORMAL_PASS"
