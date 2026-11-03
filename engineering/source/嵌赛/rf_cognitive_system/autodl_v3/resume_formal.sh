#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
CHECKPOINT="${1:-outputs/qam_aware_v3/formal/checkpoints/last.pt}"
test -f "$CHECKPOINT"
mkdir -p outputs/qam_aware_v3/formal/logs
python -m training.train_qam_aware_v3 \
  --config configs/qam_aware_v3.yaml \
  --resume "$CHECKPOINT" \
  2>&1 | tee -a outputs/qam_aware_v3/formal/logs/autodl_console.log
python -m evaluation.evaluate_qam_aware_v3 --config configs/qam_aware_v3.yaml
python -m scripts.export_qam_aware_v3_onnx --config configs/qam_aware_v3.yaml
python -m evaluation.check_qam_aware_v3_acceptance
echo "V3_AUTODL_FORMAL_RESUME_PASS"
