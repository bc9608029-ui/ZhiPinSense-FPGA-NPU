#!/usr/bin/env bash
# run_radioml_dc_dualsdr.sh -- board-side dual-SDR DC-adaptation measurement
# (fix10class24-original-radioml-dc-ab1, dual-SDR part, phase
#  radioml-original-dualsdr-ab-24class-bf16-fix10).
#
# Re-feed the SAME frozen original-RadioML test frames (short24 = one 30 dB frame per
# class) through the REAL dual-SDR RF chain -- PC owns TX (cyclic canonical burst over
# 50-ohm coax), BOARD owns RX (capture -> coarse CFO -> fine sync/gain -> wide-linear ->
# 0.100 gate -> NPU24 -> RAW-24 argmax, NO merge) -- under one of two adaptations that
# share the SAME phase name and are chosen by --adaptation:
#
#   --adaptation=direct        现有行为, 逐字节不变:
#                              iq -> cyclic tile 1024->53760 -> CI16(RMS2048) -> 恢复
#                              -> 前 1024 * unscale
#   --adaptation=dc-transport  移除原始 IQ 均值(DC) -> 只传 AC -> RX 恢复 -> 还原尺度
#                              + 加回 DC (三段式: 阶段1 RF 增益 / 阶段2 TX 尺度 / 阶段3 DC 加回)
#
# The runner resolves --adaptation fail-closed and DERIVES input_kind from it (direct =
# "radioml-original-dualsdr-ab-2p56m"; dc-transport = that + "-dc-transport").  The PC TX
# service verifies input_kind + manifest_sha256 at HELLO, so a cross-end adaptation
# mismatch is rejected IMMEDIATELY at HELLO (not discovered later).  The board loader
# validates every manifest row's adaptation tag against --adaptation (direct = 18-col,
# dc-transport = 22-col).
#
# This is a MEASUREMENT, never a regression PASS.  Forbidden tokens this script must
# never print on its own: RF_PASS, SMOKE_PASS, PROJECT_COMPLETE, FINAL_*, HOST_MATCH
# (the host judger owns those verdicts).  The board NEVER forces a classification.
#
# Dual-SDR topology: the board is RX-only and is the control-channel CLIENT; it connects
# to the Windows PC TX service (SERVER, port 39010).  On the PC you must FIRST launch the
# service with the SAME --adaptation (so input_kind + manifest_sha256 agree):
#   D:\radioconda\python.exe -I scripts/pc_tx_radioml_dualsdr.py launch \
#       --tx-payload <tx payload pkg> --adaptation=direct --tx-uri "<PC_TX_URI>"
#   D:\radioconda\python.exe -I scripts/pc_tx_radioml_dualsdr.py launch \
#       --tx-payload <dc tx payload pkg> --adaptation=dc-transport --tx-uri "<PC_TX_URI>"
#
# --input-dir is the TX-payload package (tx_manifest.tsv + route_d2_rf_manifest.tsv +
# 480 x <sid>.i16):
#   direct       18-col manifest (raw-IQ CI16 payload)
#   dc-transport 22-col manifest (AC-only CI16 payload + dc_i/dc_q/ac_rms/inverse_scale)
# The runner verifies the WHOLE package fail-closed and requires the manifest adaptation
# to equal --adaptation, and hashes route_d2_rf_manifest.tsv for the HELLO manifest_sha256.
#
# --rx-gain=35 is passed EXPLICITLY: run_gate9_rml23.sh defaults --rx-gain=10 and the
# runner resolves the LAST occurrence, so omitting it here would silently run at 10 dB.
#
# Usage (run on the board, from the project root):
#   bash scripts/run_radioml_dc_dualsdr.sh \
#       --mode=short24 --adaptation=direct \
#       --input-dir=<DIRECT tx payload package dir> \
#       --tx-control=tcp://<PC_IP>:39010 \
#       --rx-uri="<board RX SDR URI>" \
#       --out-dir=/root/rml24_dc_dualsdr_direct_$(date +%s)
#   bash scripts/run_radioml_dc_dualsdr.sh \
#       --mode=short24 --adaptation=dc-transport \
#       --input-dir=<DC tx payload package dir> \
#       --tx-control=tcp://<PC_IP>:39010 \
#       --rx-uri="<board RX SDR URI>" \
#       --out-dir=/root/rml24_dc_dualsdr_dc_$(date +%s)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Frozen 24-class BF16 model identity (NOT the 23-class ZG default in common_rml23.sh).
MODEL_JSON="$ROOT/model_rml24_bf16/rml24_adamrv11_bf16.json"
MODEL_RAW="$ROOT/model_rml24_bf16/rml24_adamrv11_bf16.raw"
MODEL_JSON_SHA="28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
MODEL_RAW_SHA="c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
PHASE="radioml-original-dualsdr-ab-24class-bf16-fix10"

# Frozen dual-SDR RF contract (red lines; the runner defaults + readback).  The board
# owns NO TX: TX config (bw/atten) belongs to the PC TX service, NOT to this script.
CENTER_HZ=2400000000
SAMPLE_RATE=2560000
RX_GAIN_DB=35.0
RX_BW=18000000
TARGET_RMS=2048.0
RF_PATH="direct-cable"

# input_kind is DERIVED by the runner from --adaptation (this script passes --adaptation
# through and does NOT pass --input-kind; the PC TX service must be launched with the
# SAME --adaptation so its --input-kind matches the board's HELLO input_kind).
DIRECT_INPUT_KIND="radioml-original-dualsdr-ab-2p56m"
DC_INPUT_KIND="${DIRECT_INPUT_KIND}-dc-transport"

MODE=""
ADAPTATION=""
INPUT_DIR=""
TX_CONTROL=""
RX_URI=""
OUT_DIR=""

usage() {
    echo "Usage: $0 --mode=short24|full480 --adaptation=direct|dc-transport --input-dir=<tx payload pkg> --tx-control=tcp://<PC_IP>:39010 --rx-uri=<SDR uri> --out-dir=<fresh dir>" >&2
    exit 2
}
for arg in "$@"; do
    case "$arg" in
        --mode=*)       MODE="${arg#--mode=}" ;;
        --adaptation=*) ADAPTATION="${arg#--adaptation=}" ;;
        --input-dir=*)  INPUT_DIR="${arg#--input-dir=}" ;;
        --tx-control=*) TX_CONTROL="${arg#--tx-control=}" ;;
        --rx-uri=*)     RX_URI="${arg#--rx-uri=}" ;;
        --out-dir=*)    OUT_DIR="${arg#--out-dir=}" ;;
        *) echo "ERROR: unknown arg: $arg" >&2; usage ;;
    esac
done

# ---- fail-closed validation (mirrors the runner's own checks) --------------
[ -n "$MODE" ] || { echo "ERROR: --mode=short24|full480 required" >&2; usage; }
[ "$MODE" = "short24" ] || [ "$MODE" = "full480" ] || {
    echo "ERROR: --mode must be short24 or full480 (got '$MODE')" >&2; exit 2; }
[ -n "$ADAPTATION" ] || { echo "ERROR: --adaptation=direct|dc-transport required" >&2; usage; }
[ "$ADAPTATION" = "direct" ] || [ "$ADAPTATION" = "dc-transport" ] || {
    echo "ERROR: --adaptation must be direct or dc-transport (got '$ADAPTATION')" >&2; exit 2; }
[ -n "$INPUT_DIR" ] || { echo "ERROR: --input-dir=<tx payload package dir> required" >&2; usage; }
[ -f "$INPUT_DIR/tx_manifest.tsv" ] || {
    echo "ERROR: tx_manifest.tsv not found in input dir: $INPUT_DIR" >&2; exit 2; }
[ -f "$INPUT_DIR/route_d2_rf_manifest.tsv" ] || {
    echo "ERROR: route_d2_rf_manifest.tsv not found in input dir (run pc_tx_radioml_dualsdr.py build-frozen-dir): $INPUT_DIR" >&2; exit 2; }
[ -n "$TX_CONTROL" ] || { echo "ERROR: --tx-control=tcp://<PC_IP>:39010 required" >&2; usage; }
[ -n "$RX_URI" ] || { echo "ERROR: --rx-uri=<board RX SDR URI> required" >&2; usage; }
[ -n "$OUT_DIR" ] || { echo "ERROR: --out-dir=<fresh dir> required" >&2; usage; }
[ -e "$OUT_DIR" ] && {
    echo "ERROR: output dir already exists (refuse overwrite): $OUT_DIR" >&2
    echo "       Use a fresh timestamped dir, e.g. /root/rml24_dc_dualsdr_\$(date +%s)." >&2
    exit 2; }
[ -f "$MODEL_JSON" ] && [ -f "$MODEL_RAW" ] || {
    echo "ERROR: frozen 24-class BF16 model artifacts missing under model_rml24_bf16/" >&2
    exit 2; }

# ---- manifest adaptation tag vs --adaptation (fail-closed, mirrors the loader) ----
if [ "$ADAPTATION" = "direct" ]; then
    expect_cols=18; expect_tag="cyclic_tile_1024_to_53760_rms2048_ci16"
else
    expect_cols=22; expect_tag="dc_transport_cyclic_tile_1024_to_53760_rms2048_ci16"
fi
mcols="$(head -n 1 "$INPUT_DIR/tx_manifest.tsv" | awk -F'\t' '{print NF}')"
[ "$mcols" = "$expect_cols" ] || {
    echo "ERROR: tx_manifest.tsv is ${mcols}-col but --adaptation=$ADAPTATION expects ${expect_cols}-col." >&2
    echo "       direct=18-col raw-IQ, dc-transport=22-col AC. Wrong input package?" >&2
    exit 2; }
bad_tag="$(awk -F'\t' 'NR>1 && $18 != "'"$expect_tag"'" {print NR; exit}' "$INPUT_DIR/tx_manifest.tsv")"
[ -z "$bad_tag" ] || {
    echo "ERROR: tx_manifest.tsv line $bad_tag has adaptation tag != $expect_tag." >&2
    exit 2; }

# ---- transcript (sibling of $OUT_DIR; moved inside after the runner creates it) ----
LOG="${OUT_DIR}.run.log"

if [ "$ADAPTATION" = "direct" ]; then INPUT_KIND="$DIRECT_INPUT_KIND"; else INPUT_KIND="$DC_INPUT_KIND"; fi
echo "RADIOML_ORIGINAL_DC_DUALSDR_START mode=$MODE adaptation=$ADAPTATION input_kind=$INPUT_KIND input_dir=$INPUT_DIR tx_control=$TX_CONTROL rx_uri=$RX_URI out_dir=$OUT_DIR model_sha=$MODEL_RAW_SHA"
echo "RADIOML_ORIGINAL_DC_DUALSDR_SAFETY dual_sdr_rx_only_board_no_tx rf_path=$RF_PATH center=$CENTER_HZ sample_rate=$SAMPLE_RATE rx_gain=$RX_GAIN_DB rx_bw=$RX_BW target_rms=$TARGET_RMS"
echo "RADIOML_ORIGINAL_DC_DUALSDR_PC_TX_HINT: on the PC, launch the service with the SAME --adaptation=$ADAPTATION (input_kind=$INPUT_KIND)"

js="$(sha256sum "$MODEL_JSON" | awk '{print $1}')"
rs="$(sha256sum "$MODEL_RAW"  | awk '{print $1}')"
[ "$js" = "$MODEL_JSON_SHA" ] || { echo "ERROR: model JSON SHA mismatch: $js" >&2; exit 2; }
[ "$rs" = "$MODEL_RAW_SHA"  ] || { echo "ERROR: model RAW SHA mismatch: $rs" >&2; exit 2; }
echo "RADIOML_ORIGINAL_DC_DUALSDR_MODEL_SHA_OK"

# ---- integration gate: the phase must be present in gate9_phase.hpp ----
if ! grep -q "$PHASE" "$ROOT/board_package/gate9_phase.hpp" 2>/dev/null; then
    echo "ERROR: board producer phase '$PHASE' NOT in board_package/gate9_phase.hpp." >&2
    echo "       Apply the dc-ab1 integrated PATCH first (it adds the phase + runner + dispatch)." >&2
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
    --adaptation="$ADAPTATION" \
    --input-dir="$INPUT_DIR" \
    --tx-control="$TX_CONTROL" \
    --rx-uri="$RX_URI" \
    --center="$CENTER_HZ" \
    --sample-rate="$SAMPLE_RATE" \
    --rx-gain="$RX_GAIN_DB" \
    --rx-bw="$RX_BW" \
    --rf-tx-target-rms="$TARGET_RMS" \
    --rf-path="$RF_PATH" \
    --out-dir="$OUT_DIR" \
    2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
set -e

if [ -d "$OUT_DIR" ]; then
    mv "$LOG" "$OUT_DIR/run.log"
    echo "RADIOML_ORIGINAL_DC_DUALSDR_END rc=$rc out_dir=$OUT_DIR run.log moved into out_dir"
else
    echo "RADIOML_ORIGINAL_DC_DUALSDR_END rc=$rc out_dir=$OUT_DIR (runner failed before mkdir; log left at $LOG)"
fi

echo "Next (host, after copying the whole \$OUT_DIR back):"
echo "  python -I scripts/judge_radioml_dc_dualsdr.py \\"
echo "      --input-package <npu-ab1 input_package> \\"
echo "      --digital <dc digital_predictions_dc.tsv> \\"
echo "      [--board-direct <direct board_results.tsv>] \\"
echo "      [--board-dc <dc-transport board_results.tsv>] \\"
echo "      --out-dir <fresh judge dir>"

exit $rc
