#!/usr/bin/env bash
# run_force_classify_wl.sh -- fix10class24-dualsdr-repeat3-audit1 Phase C driver.
# Iterate the three dual-SDR rounds and force-classify every failed_rx/<source_index>
# dump with the wide-linear-corrected tool, exporting model_input + forced_recovery.json
# under $EXPORT/<run>/<source_index>/.  Prints one TSV row per sample to stdout.
#
# Run INSIDE WSL (g++ binary + /mnt/f paths).  Never touches the board/SDR/flash.
set -euo pipefail

DATA="/mnt/f/嵌赛/fix10class24_dualsdr_repeat3_audit1_work/data/dual_repeat3/rml24_dual_2048_repeat3_2nHRBLqn"
CLEAN="/mnt/f/嵌赛/fix10class24_tx_rms_sweep1_work/sdr_rml24_fix10class24_tx_rms_sweep1/clean24_smoke"
BIN="/mnt/f/嵌赛/fix10class24_dualsdr_repeat3_audit1_work/cpp/bin/replay_fix10class24_force_classify_wl"
EXPORT="/mnt/f/嵌赛/fix10class24_dualsdr_repeat3_audit1_work/results/forced_exports"

mkdir -p "$EXPORT"

total=0
ok=0
for run in dual_bf16_rms2048_run1 dual_bf16_rms2048_run2 dual_bf16_rms2048_run3; do
  frx="$DATA/$run/failed_rx"
  [ -d "$frx" ] || { echo "MISSING $frx" >&2; continue; }
  for idx in "$frx"/*/; do
    idx=$(basename "$idx")
    dump_dir="$frx/$idx"
    total=$((total + 1))
    line=$("$BIN" --dump-dir "$dump_dir" --clean24-dir "$CLEAN" --export-dir "$EXPORT" 2>&1)
    rc=$?
    if [ $rc -eq 0 ]; then
      ok=$((ok + 1))
      printf '%s\n' "$line"
    else
      printf 'FIX10CLASS24_FORCE_CLASSIFY_WL_ERROR run=%s source_index=%s rc=%d msg=%s\n' \
        "$run" "$idx" "$rc" "$(printf '%s' "$line" | tail -1)" >&2
    fi
  done
done

printf 'FORCE_CLASSIFY_WL_TOTAL ok=%d/%d export_dir=%s\n' "$ok" "$total" "$EXPORT"
