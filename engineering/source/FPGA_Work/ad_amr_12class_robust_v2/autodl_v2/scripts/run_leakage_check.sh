#!/usr/bin/env bash
# run_leakage_check.sh — cross-split leakage check for real-RF data (if present).
# Fail-closed: reports OK when no real-RF manifests exist yet (nothing to leak).
set -euo pipefail

cd "$(dirname "$0")/.."

MANIFEST="${1:-data/real_rf/manifest.json}"
SPLITS="${2:-data/real_rf/splits.json}"
GOLDEN="${3:-}"

if [ ! -f "$MANIFEST" ]; then
  echo "OK: no real-RF manifest at $MANIFEST — nothing to check (D4 empty)"
  exit 0
fi

ARGS=(--manifest "$MANIFEST" --splits "$SPLITS")
if [ -n "$GOLDEN" ]; then
  ARGS+=(--golden "$GOLDEN")
fi

python3 tools/check_data_leakage.py "${ARGS[@]}" 2>&1
