#!/usr/bin/env bash
# run_force_classify_sweep.sh -- fix10class24-rxresidual-audit1 Phase B sweep driver.
# Runs the gate-bypassed provisional export over all 30 failed-RX dumps
# (15 capture rounds x {1500, 500}) into results/rxresidual_audit/forced_classify_export/.
# Idempotent: re-running over the same dumps overwrites with byte-identical output
# (the tool refuses to overwrite only when the input identity differs).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
CAPDIR="${CAPDIR:-$ROOT/../board_capture_extracted}"
EXPORT="${EXPORT:-$ROOT/results/rxresidual_audit/forced_classify_export}"
CLEAN="$ROOT/clean24_smoke"
TOOL="$HERE/replay_fix10class24_failed_rx_force_classify.sh"

mkdir -p "$EXPORT"
LOG="$ROOT/results/rxresidual_audit/forced_classify_sweep.log"
: > "$LOG"

n=0
fail=0
for cap in "$CAPDIR"/*/; do
    [ -d "$cap" ] || continue
    capname="$(basename "$cap")"
    for idx in 1500 500; do
        dump="$cap/failed_rx/$idx"
        if [ ! -d "$dump" ]; then
            echo "MISSING $dump" >> "$LOG"
            fail=$((fail + 1))
            continue
        fi
        if out="$(bash "$TOOL" --dump-dir "$dump" --clean24-dir "$CLEAN" \
                  --export-dir "$EXPORT" 2>&1)"; then
            echo "$out" >> "$LOG"
            n=$((n + 1))
        else
            echo "RC=$? dump=$dump" >> "$LOG"
            echo "$out" >> "$LOG"
            fail=$((fail + 1))
        fi
    done
done

echo "OK_EXPORTS=$n FAIL_EXPORTS=$fail"
echo "FORCE_CLASSIFY_LINES=$(grep -c 'FIX10CLASS24_FORCE_CLASSIFY ' "$LOG" || true)"
echo "ERROR_LINES=$(grep -c 'ERROR:' "$LOG" || true)"
exit $fail
