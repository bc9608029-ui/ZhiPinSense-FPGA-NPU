#!/usr/bin/env bash
# run_force_classify_full24_accuracy1_sweep.sh -- fix10class24-full24-accuracy1 Phase B sweep.
# Runs the gate-bypassed provisional export over every REJECTED failed-RX dump
# (<captures-dir>/failed_rx/<source_index>/) into results/full24_accuracy1/forced_classify_export/.
# Gated samples have no failed_rx dump, so iterating failed_rx/*/ naturally covers only rejects.
# Idempotent: re-running over the same dumps overwrites with byte-identical output.
#
# capture_id = basename(<captures-dir>); the C++ tool derives it from dump_dir's grandparent,
# so every export lands under export_dir/<capture_id>/<source_index>/.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
CAPDIR="${CAPDIR:-$ROOT/results/full24_accuracy1/captures}"
EXPORT="${EXPORT:-$ROOT/results/full24_accuracy1/forced_classify_export}"
CLEAN="$ROOT/clean24_smoke"
TOOL="$HERE/replay_fix10class24_failed_rx_force_classify.sh"

mkdir -p "$EXPORT"
LOG="$ROOT/results/full24_accuracy1/forced_classify_sweep.log"
: > "$LOG"

n=0
fail=0
for dump in "$CAPDIR"/failed_rx/*/; do
    [ -d "$dump" ] || continue
    if out="$(bash "$TOOL" --dump-dir "$dump" --clean24-dir "$CLEAN" \
              --export-dir "$EXPORT" 2>&1)"; then
        echo "$out" >> "$LOG"
        n=$((n + 1))
    else
        rc=$?
        echo "RC=$rc dump=$dump" >> "$LOG"
        echo "$out" >> "$LOG"
        fail=$((fail + 1))
    fi
done

echo "OK_EXPORTS=$n FAIL_EXPORTS=$fail"
echo "FORCE_CLASSIFY_LINES=$(grep -c 'FIX10CLASS24_FORCE_CLASSIFY ' "$LOG" || true)"
echo "ERROR_LINES=$(grep -c 'ERROR:' "$LOG" || true)"
exit $fail
