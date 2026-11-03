#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
mkdir -p outputs/qam_aware_v3_1/formal/logs
python -m evaluation.audit_qam_aware_v3_1_dataset --config configs/qam_aware_v3_1.yaml
python -m training.train_qam_aware_v3_1 --config configs/qam_aware_v3_1.yaml \
  2>&1 | tee outputs/qam_aware_v3_1/formal/logs/autodl_console.log
python -m evaluation.evaluate_qam_aware_v3_1 --config configs/qam_aware_v3_1.yaml
python -m scripts.export_qam_aware_v3_1_onnx --config configs/qam_aware_v3_1.yaml
python -m evaluation.check_qam_aware_v3_1_acceptance
echo "V3_1_AUTODL_FORMAL_PASS"
