#!/usr/bin/env bash
# run_residual_decompose_sweep.sh -- fix10class24-rxresidual-audit1 Phase E sweep driver.
# Runs the training-block residual decomposition over all 30 failed-RX dumps and writes
# results/rxresidual_audit/residual_attribution.tsv (one row per (capture_id, source_index)).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
CAPDIR="${CAPDIR:-$ROOT/../board_capture_extracted}"
OUT="${OUT:-$ROOT/results/rxresidual_audit/residual_attribution.tsv}"
TOOL="$HERE/replay_fix10class24_failed_rx_force_classify.sh"

mkdir -p "$(dirname "$OUT")"
TMP="$(mktemp)"
: > "$TMP"

n=0
fail=0
for cap in "$CAPDIR"/*/; do
    [ -d "$cap" ] || continue
    for idx in 500 1500; do
        dump="$cap/failed_rx/$idx"
        if [ ! -d "$dump" ]; then
            echo "MISSING $dump" >&2
            fail=$((fail + 1))
            continue
        fi
        if row="$(bash "$TOOL" --decompose --dump-dir "$dump" 2>/dev/null)"; then
            printf '%s\n' "$row" >> "$TMP"
            n=$((n + 1))
        else
            echo "RC=$? dump=$dump" >&2
            fail=$((fail + 1))
        fi
    done
done

{
    printf 'capture_id\tsource_index\tresidual_before\tresidual_before_validation\tcorr_before\t'
    printf 'const_phase_resid_train\tconst_phase_resid_val\tconst_phase_corr_val\tconst_phase_imp\t'
    printf 'residual_cfo_resid_train\tresidual_cfo_resid_val\tresidual_cfo_corr_val\tresidual_cfo_imp\tresidual_cfo_hz\t'
    printf 'wide_linear_resid_train\twide_linear_resid_val\twide_linear_corr_val\twide_linear_imp\twide_linear_image_ratio\t'
    printf 'fir5_resid_train\tfir5_resid_val\tfir5_corr_val\tfir5_imp\tattribution\n'
    sort -t$'\t' -k1,1 -k2,2n "$TMP"
} > "$OUT"
rm -f "$TMP"

echo "RESIDUAL_DECOMPOSE_SWEEP_OK samples=$n fail=$fail out=$OUT"
exit "$fail"
