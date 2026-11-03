#!/usr/bin/env bash
set -euo pipefail

# Run the first five epochs of the *formal* trajectory.  If the curves and
# finite-value checks are healthy, continue the exact same checkpoint with
# resume_formal.sh instead of paying for a second training run.
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export CUBLAS_WORKSPACE_CONFIG=:4096:8
python -m evaluation.audit_qam_aware_v3_2_dataset --config configs/qam_aware_v3_2.yaml
python -m training.train_qam_aware_v3_2 \
  --config configs/qam_aware_v3_2.yaml \
  --stop-after-epoch 5 \
  2>&1 | tee outputs/qam_aware_v3_2/formal/logs/autodl_pilot_console.log
echo "V3_2_AUTODL_PILOT_PASS"
