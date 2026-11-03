#!/usr/bin/env bash
set -euo pipefail

# Resume the three-seed formal stage only (skip smoke / ablation / selection).
# Completed seeds are skipped and incomplete seeds resume from their own last.pt.
# The frozen selected_candidate.yaml is required and is never re-derived.
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export CUBLAS_WORKSPACE_CONFIG=:4096:8

ROOT="outputs/qam_aware_v3_2"
SELECTED="$ROOT/formal/selected_candidate.yaml"
LOG_DIR="$ROOT/formal/logs"
mkdir -p "$LOG_DIR"

test -f "$SELECTED" || { echo "selected_candidate.yaml not found; run run_complete.sh first" >&2; exit 2; }

set +o pipefail
python -m scripts.run_qam_aware_v3_2_formal \
  --config configs/qam_aware_v3_2.yaml \
  --selected "$SELECTED" \
  --gates configs/qam_aware_v3_2_acceptance.yaml \
  2>&1 | tee -a "$LOG_DIR/autodl_console.log"
FORMAL_RC=${PIPESTATUS[0]}
set -o pipefail
if [[ "$FORMAL_RC" -ne 0 && "$FORMAL_RC" -ne 2 ]]; then
  echo "Formal training failed with exit code $FORMAL_RC" >&2
  exit "$FORMAL_RC"
fi

python -m scripts.package_qam_aware_v3_2_results

if [[ "$FORMAL_RC" -eq 0 ]]; then
  echo "V3_2_AUTODL_FORMAL_RESUME_PASS"
  echo "Download: $ROOT/qam_aware_v3_2_formal_results.tar.gz"
else
  echo "V3_2_AUTODL_FORMAL_RESUME_GATE_FAILED"
  echo "Download the result archive for diagnosis: $ROOT/qam_aware_v3_2_formal_results.tar.gz"
  exit "$FORMAL_RC"
fi
