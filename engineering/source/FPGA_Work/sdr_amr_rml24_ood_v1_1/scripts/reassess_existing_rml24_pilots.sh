#!/usr/bin/env bash
# Reassess existing RML24 pilot checkpoints on a single unified validation index set.
#
# Never retrains, never touches the test split, and never reads the old (buggy)
# baseline rated_0_20 values: every trial's best.pt is re-scored from scratch on the
# frozen validation split, then a multi-metric ranking + formal candidate plan are
# rebuilt.  The single result line is emitted by the backing module:
#   RML24_PILOT_REASSESS result=PASS|FAIL
#
# Usage: scripts/reassess_existing_rml24_pilots.sh --pilot-root <dir> \
#          [--eval-samples N] [--index-seed S] [--output-dir D]
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

PILOT_ROOT=""
EVAL_SAMPLES=""
INDEX_SEED=""
OUTPUT_DIR=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --pilot-root) PILOT_ROOT="$2"; shift 2 ;;
    --eval-samples) EVAL_SAMPLES="$2"; shift 2 ;;
    --index-seed) INDEX_SEED="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$PILOT_ROOT" ]; then
  echo "usage: $0 --pilot-root <existing pilot output root> [--eval-samples N] [--index-seed S] [--output-dir D]" >&2
  exit 2
fi

ARGS=(--pilot-root "$PILOT_ROOT")
if [ -n "$EVAL_SAMPLES" ]; then ARGS+=(--eval-samples "$EVAL_SAMPLES"); fi
if [ -n "$INDEX_SEED" ]; then ARGS+=(--index-seed "$INDEX_SEED"); fi
if [ -n "$OUTPUT_DIR" ]; then ARGS+=(--output-dir "$OUTPUT_DIR"); fi

"$PYTHON" -m scripts.reassess_rml24_pilots \
  --config configs/rml24_base.yaml \
  --search-space configs/search_space_rml24.yaml \
  "${ARGS[@]}"
