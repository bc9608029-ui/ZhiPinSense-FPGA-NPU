#!/usr/bin/env bash
# run_radioml_singlesdr_ab.sh -- board-side single-SDR measurement
# (fix10class24-original-radioml-singlesdr-ab1, phase
#  radioml-original-singlesdr-ab-24class-bf16-fix10).
#
# Re-feed the SAME 480 frozen original-RadioML test frames (via the dualsdr TX-derived
# CI16 payload package) through the REAL single-SDR RF chain -- ONE Pluto: local TX ->
# 50-ohm SMA coax -> the SAME Pluto RX (loopback=0) -> the frozen 24-class BF16 NPU --
# for the 4-arm A/D/C/S comparison (arm S).
#
# This is a MEASUREMENT, never a regression PASS.  Forbidden tokens this script must
# never print on its own: RF_PASS, SMOKE_PASS, PROJECT_COMPLETE, FINAL_*, HOST_MATCH
# (the host judger owns those verdicts).  The board NEVER forces a classification.
#
# Single-SDR topology: NO PC TX service.  The runner owns the TX locally (transfer_one
# _attempt_rf_24class_bf16_fix10), does its own negative control (stop TX -> confirm ->
# RX noise floor) and single-device restore.  There is NO TCP control channel.
#
# --input-dir is the TX-derived payload package (tx_manifest.tsv + 480 x <sid>.i16),
# written on the host by scripts/export_radioml_dualsdr_tx_payload.py -- NOT the
# npu-ab1 [2,1024] .bin package.  The runner verifies the whole package fail-closed.
#
# --rx-gain=35 is passed EXPLICITLY: run_gate9_rml23.sh defaults --rx-gain=10 and the
# runner resolves the LAST occurrence, so omitting it here would silently run at 10 dB.
#
# Usage (run on the board, from the project root):
#   bash scripts/run_radioml_singlesdr_ab.sh \
#       --mode=short24 \
#       --input-dir=<tx payload package dir> \
#       --rx-uri="<single SDR URI (TX+RX)>" \
#       --out-dir=/root/rml24_singlesdr_ab_<timestamp>
#
#   (then re-run with --mode=full480 for the complete measurement)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Frozen 24-class BF16 model identity (NOT the 23-class ZG default in common_rml23.sh).
MODEL_JSON="$ROOT/model_rml24_bf16/rml24_adamrv11_bf16.json"
MODEL_RAW="$ROOT/model_rml24_bf16/rml24_adamrv11_bf16.raw"
MODEL_JSON_SHA="28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
MODEL_RAW_SHA="c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
PHASE="radioml-original-singlesdr-ab-24class-bf16-fix10"

# Frozen single-SDR RF contract (red lines; the runner defaults + readback).
CENTER_HZ=2400000000
SAMPLE_RATE=2560000
RX_GAIN_DB=35.0
RX_BW=18000000
TX_BW=18000000
TX_ATTEN_DB=-40.0
TARGET_RMS=2048.0
RF_PATH="direct-cable"

MODE=""
INPUT_DIR=""
RX_URI=""
OUT_DIR=""

usage() {
    echo "Usage: $0 --mode=short24|full480 --input-dir=<tx payload pkg> --rx-uri=<SDR uri> --out-dir=<fresh dir>" >&2
    exit 2
}
for arg in "$@"; do
    case "$arg" in
        --mode=*)       MODE="${arg#--mode=}" ;;
        --input-dir=*)  INPUT_DIR="${arg#--input-dir=}" ;;
        --rx-uri=*)     RX_URI="${arg#--rx-uri=}" ;;
        --out-dir=*)    OUT_DIR="${arg#--out-dir=}" ;;
        *) echo "ERROR: unknown arg: $arg" >&2; usage ;;
    esac
done

# ---- fail-closed validation (mirrors the runner's own checks) --------------
[ -n "$MODE" ] || { echo "ERROR: --mode=short24|full480 required" >&2; usage; }
[ "$MODE" = "short24" ] || [ "$MODE" = "full480" ] || {
    echo "ERROR: --mode must be short24 or full480 (got '$MODE')" >&2; exit 2; }
[ -n "$INPUT_DIR" ] || { echo "ERROR: --input-dir=<tx payload package dir> required" >&2; usage; }
[ -f "$INPUT_DIR/tx_manifest.tsv" ] || {
    echo "ERROR: tx_manifest.tsv not found in input dir: $INPUT_DIR" >&2; exit 2; }
[ -n "$RX_URI" ] || { echo "ERROR: --rx-uri=<single SDR URI (TX+RX)> required" >&2; usage; }
[ -n "$OUT_DIR" ] || { echo "ERROR: --out-dir=<fresh dir> required" >&2; usage; }
[ -e "$OUT_DIR" ] && {
    echo "ERROR: output dir already exists (refuse overwrite): $OUT_DIR" >&2
    echo "       Use a fresh timestamped dir, e.g. /root/rml24_singlesdr_ab_\$(date +%s)." >&2
    exit 2; }
[ -f "$MODEL_JSON" ] && [ -f "$MODEL_RAW" ] || {
    echo "ERROR: frozen 24-class BF16 model artifacts missing under model_rml24_bf16/" >&2
    exit 2; }

# ---- transcript (sibling of $OUT_DIR; moved inside after the runner creates it) ----
LOG="${OUT_DIR}.run.log"

echo "RADIOML_ORIGINAL_SINGLESDR_AB_START mode=$MODE input_dir=$INPUT_DIR rx_uri=$RX_URI out_dir=$OUT_DIR model_sha=$MODEL_RAW_SHA"
echo "RADIOML_ORIGINAL_SINGLESDR_AB_SAFETY single_sdr_local_tx_no_pc_tx rf_path=$RF_PATH center=$CENTER_HZ sample_rate=$SAMPLE_RATE rx_gain=$RX_GAIN_DB rx_bw=$RX_BW tx_bw=$TX_BW tx_atten=$TX_ATTEN_DB target_rms=$TARGET_RMS"

js="$(sha256sum "$MODEL_JSON" | awk '{print $1}')"
rs="$(sha256sum "$MODEL_RAW"  | awk '{print $1}')"
[ "$js" = "$MODEL_JSON_SHA" ] || { echo "ERROR: model JSON SHA mismatch: $js" >&2; exit 2; }
[ "$rs" = "$MODEL_RAW_SHA"  ] || { echo "ERROR: model RAW SHA mismatch: $rs" >&2; exit 2; }
echo "RADIOML_ORIGINAL_SINGLESDR_AB_MODEL_SHA_OK"

# ---- integration gate: the phase must be present in gate9_phase.hpp ----
if ! grep -q "$PHASE" "$ROOT/board_package/gate9_phase.hpp" 2>/dev/null; then
    echo "ERROR: board producer phase '$PHASE' NOT in board_package/gate9_phase.hpp." >&2
    echo "       Apply the singlesdr-ab1 PATCH first (it adds the phase + runner + dispatch)." >&2
    echo "       This script will not silently run a missing phase -- exit 2." >&2
    exit 2
fi

set +e
bash "$ROOT/scripts/run_gate9_rml23.sh" \
    --phase="$PHASE" \
    --model-json="$MODEL_JSON" \
    --model-raw="$MODEL_RAW" \
    --model-sha="$MODEL_RAW_SHA" \
    --mode="$MODE" \
    --input-dir="$INPUT_DIR" \
    --rx-uri="$RX_URI" \
    --center="$CENTER_HZ" \
    --sample-rate="$SAMPLE_RATE" \
    --rx-gain="$RX_GAIN_DB" \
    --rx-bw="$RX_BW" \
    --tx-bw="$TX_BW" \
    --tx-atten="$TX_ATTEN_DB" \
    --rf-tx-target-rms="$TARGET_RMS" \
    --rf-path="$RF_PATH" \
    --out-dir="$OUT_DIR" \
    2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
set -e

if [ -d "$OUT_DIR" ]; then
    mv "$LOG" "$OUT_DIR/run.log"
    echo "RADIOML_ORIGINAL_SINGLESDR_AB_END rc=$rc out_dir=$OUT_DIR run.log moved into out_dir"
else
    echo "RADIOML_ORIGINAL_SINGLESDR_AB_END rc=$rc out_dir=$OUT_DIR (runner failed before mkdir; log left at $LOG)"
fi

echo "Next (host, after copying the whole \$OUT_DIR back):"
echo "  python -I scripts/judge_radioml_singlesdr.py \\"
echo "      --input-package <npu-ab1 input_package> \\"
echo "      --digital <dualsdr digital_roundtrip.tsv> \\"
echo "      [--board-dualsdr <dualsdr board_results.tsv>] \\"
echo "      --board-singlesdr <\$OUT_DIR/board_results.tsv> \\"
echo "      --out-dir <fresh judge dir>"

exit $rc
