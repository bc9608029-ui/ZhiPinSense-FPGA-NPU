#!/usr/bin/env bash
# M6-M8: bounded 24-class hyperparameter pilot -> dedupe/select -> formal (validation-only).
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

CONFIG="configs/rml24_base.yaml"
SEARCH="configs/search_space_rml24.yaml"
PILOT_ROOT="runs/rml24_base/pilot"
CANDIDATES="runs/rml24_base/pilot/pilot_unique_candidates.json"

echo "[train] pilot (Optuna TPE, bounded trials)"
"$PYTHON" -m training.rml24_pilot --config "$CONFIG" --search-space "$SEARCH"

# Frozen pilot seed (no ls|sort|tail guessing); fail closed if the directory is absent.
PILOT_SEED="$("$PYTHON" -c 'import yaml,sys;print(yaml.safe_load(open(sys.argv[1],encoding="utf-8"))["search"]["pilot_seed"])' "$SEARCH")"
PILOT_SEED_DIR="$PILOT_ROOT/seed$PILOT_SEED"
if [ ! -d "$PILOT_SEED_DIR" ]; then
  echo "pilot produced no directory at $PILOT_SEED_DIR" >&2
  exit 1
fi

echo "[train] select (dedupe by candidate signature, then rank; validation-only)"
"$PYTHON" -m training.rml24_select --config "$CONFIG" --search-space "$SEARCH" \
  --pilot-root "$PILOT_SEED_DIR"

if [ ! -f "$CANDIDATES" ]; then
  echo "select produced no candidate plan at $CANDIDATES" >&2
  exit 1
fi

echo "[train] formal (frozen budget: 1 candidate x 3 seeds; dedup/resume)"
"$PYTHON" -m training.rml24_formal --config "$CONFIG" --search-space "$SEARCH" \
  --candidates "$CANDIDATES"

echo "RML24_TRAIN_OK"
