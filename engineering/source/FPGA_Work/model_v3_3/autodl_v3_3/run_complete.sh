#!/usr/bin/env bash
set -euo pipefail

# One-command V3.3 workflow.  Safe to re-run after an interruption:
#   * preflight is now a CUDA hard gate (real-model CUDA integration test) and is
#     hash-guarded together with the pilot (kept unless their inputs changed);
#   * a completed seed is skipped (its SEED_DONE.json marker exists);
#   * an incomplete seed resumes from its own checkpoints/last.pt;
#   * the frozen selected_candidate.yaml is never re-derived or silently changed;
#   * the formal stage is forbidden unless the pilot produced selected_candidate;
#   * PASS is printed only after every stage completes.
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export CUBLAS_WORKSPACE_CONFIG=:4096:8

ROOT="outputs/qam_aware_v3_3"
SELECTED="$ROOT/formal/selected_candidate.yaml"
LOG_DIR="$ROOT/formal/logs"
mkdir -p "$LOG_DIR"

echo "[1/6] Checking CUDA and installing non-Torch dependencies"
bash autodl_v3_3/setup_env.sh

echo "[2/6] Preflight (CUDA hard gate: real-model CUDA test + source tests + 2-epoch train/eval/export)"
bash autodl_v3_3/run_preflight.sh

# Hard gate: the CUDA preflight marker must exist and record a source-hash match.
# run_preflight.sh already verifies the hash (re-running on mismatch) and set -e
# aborts on any step, so a surviving marker here is a genuine CUDA preflight pass.
PREFLIGHT_MARKER="$ROOT/preflight/V3_3_PREFLIGHT_DONE"
test -f "$PREFLIGHT_MARKER" || { echo "CUDA preflight marker missing; preflight did not complete" >&2; exit 2; }
grep -q "passed hash=" "$PREFLIGHT_MARKER" || { echo "CUDA preflight marker malformed" >&2; exit 2; }
echo "CUDA preflight gate passed ($(grep 'passed hash=' "$PREFLIGHT_MARKER"))"

echo "[3/6] Pilot (performance gate: Stage-1 ablation + validation/OOD selection + threshold)"
bash autodl_v3_3/run_pilot.sh

echo "[4/6] Verifying the zero-gate initialization reproduces V2 exactly"
python -m scripts.verify_qam_aware_v3_3_init --config configs/qam_aware_v3_3.yaml

# The formal stage is entered only after the pilot produced a promotion decision.
test -f "$SELECTED" || { echo "selected_candidate.yaml missing; pilot did not produce a valid candidate" >&2; exit 2; }
test -f "$ROOT/ablation/access_audit.json" || { echo "pilot access_audit.json missing; selection isolation not proven" >&2; exit 2; }
if ! grep -q "promoted" "$SELECTED"; then
  echo "selected_candidate.yaml is malformed (missing 'promoted')" >&2
  exit 2
fi
if grep -q "promoted: false" "$SELECTED"; then
  echo "Pilot did not promote a trained candidate (A0 won or a pilot gate failed);"
  echo "V2 stays champion and the three-seed formal run is skipped."
  echo "V3_3_AUTODL_COMPLETE_NO_PROMOTION"
  exit 0
fi

echo "[5/6] Three-seed formal trajectory (per-seed resume/skip + multi-seed gate)"
set +o pipefail
python -m scripts.run_qam_aware_v3_3_formal \
  --config configs/qam_aware_v3_3.yaml \
  --selected "$SELECTED" \
  --gates configs/qam_aware_v3_3_acceptance.yaml \
  2>&1 | tee -a "$LOG_DIR/autodl_console.log"
FORMAL_RC=${PIPESTATUS[0]}
set -o pipefail
if [[ "$FORMAL_RC" -ne 0 && "$FORMAL_RC" -ne 2 ]]; then
  echo "Formal training failed with exit code $FORMAL_RC (see $LOG_DIR/autodl_console.log)" >&2
  exit "$FORMAL_RC"
fi
ACCEPTANCE_RC=$FORMAL_RC

echo "[6/6] Packaging all formal artifacts (per-seed + aggregate)"
python -m scripts.package_qam_aware_v3_3_results

if [[ "$ACCEPTANCE_RC" -eq 0 ]]; then
  echo "V3_3_AUTODL_COMPLETE_PASS"
  echo "Download: $ROOT/qam_aware_v3_3_formal_results.tar.gz"
  exit 0
fi

echo "V3_3_AUTODL_COMPLETE_TRAINED_BUT_GATE_FAILED"
echo "Three-seed training/evaluation/export completed, but V3.3 remains a challenger and V2 stays frozen as champion."
echo "Download the result archive for diagnosis: $ROOT/qam_aware_v3_3_formal_results.tar.gz"
exit "$ACCEPTANCE_RC"
