#!/usr/bin/env bash
# run_force_classify_full24_sweep.sh -- fix10class24-full24-failed-rx-forceclass1 Phase B sweep.
# Runs the gate-bypassed provisional export over all 20 flat failed-RX dumps
# (failed_rx/<source_index>/) into results/full24_failed_rx_forceclass/forced_classify_export/.
# Idempotent: re-running over the same dumps overwrites with byte-identical output.
#
# Layout note: this archive is FLAT (no per-round capture_id nesting).  The C++ tool derives
# capture_id from dump_dir's grandparent, so every export lands under a single capture bucket
# named after the extract root.  Primary key = source_index (20 unique).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
CAPROOT="${CAPROOT:-$ROOT/../board_capture_extracted/rml24_full24_failed_rx_1773374413}"
EXPORT="${EXPORT:-$ROOT/results/full24_failed_rx_forceclass/forced_classify_export}"
CLEAN="$ROOT/clean24_smoke"
TOOL="$HERE/replay_fix10class24_failed_rx_force_classify.sh"

mkdir -p "$EXPORT"
LOG="$ROOT/results/full24_failed_rx_forceclass/forced_classify_sweep.log"
: > "$LOG"

n=0
fail=0
for dump in "$CAPROOT"/failed_rx/*/; do
    [ -d "$dump" ] || continue
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

echo "OK_EXPORTS=$n FAIL_EXPORTS=$fail"
echo "FORCE_CLASSIFY_LINES=$(grep -c 'FIX10CLASS24_FORCE_CLASSIFY ' "$LOG" || true)"
echo "ERROR_LINES=$(grep -c 'ERROR:' "$LOG" || true)"
exit $fail
