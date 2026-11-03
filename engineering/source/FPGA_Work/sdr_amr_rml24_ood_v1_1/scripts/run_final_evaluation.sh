#!/usr/bin/env bash
# M16: offline 12-vs-24 final evaluation + model recommendation (model-side only).
# Frozen-threshold: reads the write-once ood_threshold_manifest.json; the RadioML
# test split and ood_final_test family are each read exactly once (one-time ledger).
#
# --closed-set-only: run ONLY the 24-class closed-set test (evaluate_rml24(test) once),
# never touching OOD.  Uses its own one-time ledger and does not require an
# ood_threshold_manifest.json.
#
# Usage:
#   scripts/run_final_evaluation.sh <final_checkpoint_manifest.json> \
#       <ood_threshold_manifest.json> [--twelve-class-config C] [--twelve-class-checkpoint CKPT]
#   scripts/run_final_evaluation.sh <final_checkpoint_manifest.json> --closed-set-only
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <final_checkpoint_manifest.json> [<ood_threshold_manifest.json> | --closed-set-only]" >&2
  exit 2
fi
MANIFEST="$1"; shift

CLOSED_SET_ONLY=0
THRESHOLD_MANIFEST=""
if [ "${1:-}" = "--closed-set-only" ]; then
  CLOSED_SET_ONLY=1
  shift
else
  THRESHOLD_MANIFEST="${1:-}"; shift
  if [ -z "$THRESHOLD_MANIFEST" ]; then
    echo "usage: $0 <final_checkpoint_manifest.json> [<ood_threshold_manifest.json> | --closed-set-only]" >&2
    exit 2
  fi
fi

if [ ! -f "$MANIFEST" ]; then
  echo "missing manifest: $MANIFEST" >&2
  exit 1
fi
if [ "$CLOSED_SET_ONLY" -eq 0 ] && [ ! -f "$THRESHOLD_MANIFEST" ]; then
  echo "missing threshold manifest: $THRESHOLD_MANIFEST" >&2
  exit 1
fi

if [ "$CLOSED_SET_ONLY" -eq 1 ]; then
  "$PYTHON" -m scripts.run_final_evaluation --config configs/rml24_base.yaml \
    --checkpoint-manifest "$MANIFEST" --closed-set-only "$@"
  echo "RML24_CLOSED_SET_FINAL_OK"
else
  "$PYTHON" -m scripts.run_final_evaluation --config configs/rml24_base.yaml \
    --checkpoint-manifest "$MANIFEST" --threshold-manifest "$THRESHOLD_MANIFEST" "$@"
  echo "RML24_FINAL_EVALUATION_OK"
fi
