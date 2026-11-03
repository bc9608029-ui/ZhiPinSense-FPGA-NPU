#!/usr/bin/env bash
# run_all.sh — V2 full pipeline (AutoDL GPU).
#
# Order: offline gates (preflight, data audit, leakage check) -> baseline
# reproduce -> pilot -> select -> formal -> export ONNX -> fake-int8.
# Fails fast on the first step that returns non-zero.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "== [1/10] setup_env =="
bash scripts/setup_env.sh

echo "== [2/10] preflight (offline gate) =="
bash scripts/run_preflight.sh

echo "== [3/10] data audit =="
bash scripts/run_data_audit.sh

echo "== [4/10] leakage check =="
bash scripts/run_leakage_check.sh

echo "== [5/10] baseline reproduce (Phase 1) =="
bash scripts/run_baseline_reproduce.sh

echo "== [6/10] pilot search =="
bash scripts/run_pilot.sh

echo "== [7/10] select candidates =="
bash scripts/run_select.sh --pilot-root "$(ls -d outputs/v2/pilot/seed* 2>/dev/null | head -n1)"

echo "== [8/10] formal multi-seed training =="
SELECTED="$(dirname "$(find outputs/v2 -name selected_candidates.json 2>/dev/null | head -n1)")"
bash scripts/run_formal.sh --candidates "$SELECTED/selected_candidates.json"

echo "== [9/10] export ONNX =="
# Point at a trained best.pt; adjust path as needed for the selected candidate.
bash scripts/run_export_onnx.sh --checkpoint "$(find outputs/v2 -name best.pt 2>/dev/null | head -n1)"

echo "== [10/10] fake-int8 check =="
bash scripts/run_fake_int8.sh --checkpoint "$(find outputs/v2 -name best.pt 2>/dev/null | head -n1)"

echo "run_all done"
