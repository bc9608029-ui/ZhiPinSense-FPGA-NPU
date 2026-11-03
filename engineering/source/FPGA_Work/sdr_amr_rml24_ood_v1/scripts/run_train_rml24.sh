#!/usr/bin/env bash
# M6-M8: bounded 24-class hyperparameter pilot -> select -> formal (validation-only).
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

CONFIG="configs/rml24_base.yaml"
SEARCH="configs/search_space_rml24.yaml"
PILOT_ROOT="runs/rml24_base/pilot"
CANDIDATES="runs/rml24_base/selected_candidates.json"

echo "[train] pilot (Optuna TPE, bounded trials)"
"$PYTHON" -m training.rml24_pilot --config "$CONFIG" --search-space "$SEARCH"

PILOT_SEED_DIR="$(ls -d "$PILOT_ROOT"/seed* 2>/dev/null | sort | tail -n 1)"
if [ -z "$PILOT_SEED_DIR" ]; then
  echo "pilot produced no seed directory under $PILOT_ROOT" >&2
  exit 1
fi

echo "[train] select (promote top candidates, validation-only)"
"$PYTHON" -m training.rml24_select --config "$CONFIG" --search-space "$SEARCH" \
  --pilot-root "$PILOT_SEED_DIR" --output "$CANDIDATES"

echo "[train] formal (multi-seed full budget)"
"$PYTHON" -m training.rml24_formal --config "$CONFIG" --search-space "$SEARCH" \
  --candidates "$CANDIDATES"

echo "RML24_TRAIN_OK"
