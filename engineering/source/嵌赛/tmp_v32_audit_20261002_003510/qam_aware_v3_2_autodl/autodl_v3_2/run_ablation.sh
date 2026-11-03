#!/usr/bin/env bash
set -euo pipefail

# Small controlled search (A1-A3) on train/validation only.  A0 is the frozen
# V2 reference.  Each candidate shares the same V2-initialized backbone +
# zero-gated QAM delta branch and differs only in the loss.  Results land in
# outputs/qam_aware_v3_2/ablation/{ablation_comparison.csv,ablation_summary.json}.
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
python -m training.train_qam_aware_v3_2_ablation --config configs/qam_aware_v3_2_ablation.yaml
echo "V3_2_AUTODL_ABLATION_PASS"
