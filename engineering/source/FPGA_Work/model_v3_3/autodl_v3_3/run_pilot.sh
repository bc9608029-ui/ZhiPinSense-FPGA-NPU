#!/usr/bin/env bash
set -euo pipefail

# Pilot: the PERFORMANCE gate for the formal stage.
#
#   [1] Stage-1 ablation (A0-A3, two selection seeds) — training + validation-only
#       evaluation + synthetic OOD, all on the validation namespace (never test or
#       the final blind set); a split-access audit is saved.
#   [2] Preliminary selection: name the winning mechanism and check the
#       preliminary improvement threshold (an A0 win or a below-threshold trained
#       candidate stops the search here).
#   [3] Narrow search on the ACTUAL winning mechanism (8 trials x 6 epochs, best
#       re-confirmed at the full 15 epochs on both seeds) — the tuned candidate is
#       kept only if it actually improves the untuned winner.
#   [4] Final selection + full pilot hard gates (improvement, per-seed macro-F1,
#       per-seed OOD worst-domain, per-seed per-class, per-seed FPGA-sim gaps, and
#       no NaN/Inf/missing).  Any gate failure -> promoted=false.
#   [5] Freeze the truly winning model/training config into selected_candidate.
#
# run_complete.sh refuses to enter the three-seed formal run unless this script
# produced a valid selected_candidate.yaml with a promotion decision.  A hash
# guard lets a rerun keep a previous result unless any of the model, trainer +
# resume core, evaluator, selection, acceptance, dataset/channel config, the
# search code, the pilot gate config, the resume-related tests, or the V2
# checkpoint changed.

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export CUBLAS_WORKSPACE_CONFIG=:4096:8

ROOT="outputs/qam_aware_v3_3"
MARKER="$ROOT/ablation/V3_3_PILOT_DONE"
SUMMARY="$ROOT/ablation/ablation_summary.json"
SELECTED="$ROOT/formal/selected_candidate.yaml"
mkdir -p "$(dirname "$MARKER")" "$(dirname "$SELECTED")"

V2_CHECKPOINT="init/v2_time_power_phase_best.pt"
V2_HASH=$(sha256sum "$V2_CHECKPOINT" | cut -d' ' -f1)

INPUT_HASH=$(
  cat \
    configs/qam_aware_v3_3_stage1.yaml \
    configs/qam_aware_v3_3.yaml \
    configs/qam_aware_v3_3_acceptance.yaml \
    configs/baseline.yaml \
    scripts/run_qam_aware_v3_3_stage1.py \
    training/train_qam_aware_v3_3_stage1.py \
    training/train_qam_aware_v3_3.py \
    training/qam_aware_v3_3_trainer.py \
    training/resumable_trainer.py \
    training/trainer.py \
    training/utils.py \
    tests/test_qam_aware_v3_3_cuda.py \
    tests/test_qam_aware_v3_3_trainer.py \
    training/select_qam_aware_v3_3_candidate.py \
    training/narrow_search_v3_3.py \
    training/v3_3_split_guard.py \
    evaluation/evaluate_qam_aware_v3_3.py \
    evaluation/evaluate_qam_aware_v3_3_ood.py \
    models/qam_aware_rfnet_v3_3.py \
  | sha256sum | cut -d' ' -f1
)
FULL_HASH=$(printf '%s %s\n' "$INPUT_HASH" "$V2_HASH" | sha256sum | cut -d' ' -f1)

if [[ -f "$MARKER" ]] && grep -q "$FULL_HASH" "$MARKER" && [[ -f "$SELECTED" ]]; then
  echo "Pilot already done for this input hash ($FULL_HASH); reusing selected_candidate.yaml."
  if grep -q "promoted: false" "$SELECTED"; then
    echo "V3_3_PILOT_PERFORMANCE_PASS (no promotion: A0 won or a pilot gate failed)"
  else
    echo "V3_3_PILOT_PERFORMANCE_PASS (trained candidate promoted)"
  fi
  exit 0
fi

echo "[pilot] Running Stage-1 ablation + narrow search + final selection in one pass"
python -m scripts.run_qam_aware_v3_3_stage1 \
  --config configs/qam_aware_v3_3_stage1.yaml \
  --out "$SELECTED"

test -f "$SELECTED" || { echo "selected_candidate.yaml was not produced" >&2; exit 2; }
test -f "$SUMMARY" || { echo "ablation_summary.json was not produced" >&2; exit 2; }
test -f "$ROOT/ablation/access_audit.json" || { echo "access_audit.json was not produced" >&2; exit 2; }

echo "[pilot] Final promotion decision:"
python - "$SELECTED" <<'PY'
import json, sys, yaml
path = sys.argv[1]
with open(path, encoding="utf-8") as fh:
    candidate = yaml.safe_load(fh)
print("  selected_variant:", candidate.get("selected_variant"))
print("  promoted:", candidate.get("promoted"))
print("  promotion_blocked_by:", candidate.get("promotion_blocked_by"))
print("  narrow_search_ran:", candidate.get("narrow_search_ran"))
report = candidate.get("pilot_gate_report") or {}
for variant, status in report.items():
    if not status.get("hard_gates_passed") or not status.get("improvement_ok"):
        for failure in status.get("failures", []):
            print(f"  PILOT GATE FAILED [{variant}] {failure.get('gate')} seed={failure.get('seed')} {failure.get('detail')}")
PY

printf 'passed hash=%s\n' "$FULL_HASH" > "$MARKER"

if grep -q "promoted: false" "$SELECTED"; then
  echo "V3_3_PILOT_PERFORMANCE_PASS (no promotion: A0 won or a pilot gate failed)"
else
  echo "V3_3_PILOT_PERFORMANCE_PASS (trained candidate promoted)"
fi
