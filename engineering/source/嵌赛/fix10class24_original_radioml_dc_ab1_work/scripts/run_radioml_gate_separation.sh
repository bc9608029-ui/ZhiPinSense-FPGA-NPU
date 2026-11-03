#!/usr/bin/env bash
# run_radioml_gate_separation.sh -- board-side classification/fidelity gate-separation
# measurement (fix10class24-classification-gate-separation1, Part B diagnostic bypass).
#
# Wraps the SAME single/dual SDR direct/DC runners (radioml_singlesdr_ab_runner.hpp /
# radioml_dualsdr_ab_runner.hpp) and simply toggles the NEW Part B flag
# --diagnostic-force-classify (default OFF).  Production behaviour is IDENTICAL when the
# flag is OFF -- the 0.100 fidelity gate, 19-col board_results.tsv, gated/board_pred/
# gate_reject semantics are all unchanged.  When ON, a frame whose SOLE rejection is
# 0.10 < residual <= 0.30 but whose alignment + validity still pass is re-recovered and
# classified DIAGNOSTICALLY into a SEPARATE board_diagnostic_results.tsv
# (classification_layer=NPU_BF16_DIAGNOSTIC, diagnostic_gate_bypass=1).  The production
# gate is never rewritten.
#
# Forbidden tokens this script must never print on its own: RF_PASS, SMOKE_PASS,
# PROJECT_COMPLETE, FINAL_*, HOST_MATCH (the host judger owns those verdicts).  The board
# NEVER forces a classification (hard_invalid is never bypassed to success).
#
# Topology (unchanged from the dc-ab1 runners):
#   single-SDR: NO PC TX; the runner owns local TX -> coax -> same-SDR RX, its own
#               negative control, single-device restore.  No TCP control channel.
#   dual-SDR:   board is RX-only CLIENT; PC owns TX (SERVER, port 39010).  You must FIRST
#               launch the PC TX service with the SAME --adaptation.
#
# --rx-gain=35 is passed EXPLICITLY (run_gate9_rml23.sh defaults --rx-gain=10).
#
# Usage (run on the board, from the project root):
#   # single-SDR direct, diagnostic bypass ON
#   bash scripts/run_radioml_gate_separation.sh \
#       --sdr=single --mode=short24 --adaptation=direct --diagnostic-force-classify \
#       --input-dir=<DIRECT tx payload pkg> \
#       --rx-uri="<single SDR URI (TX+RX)>" \
#       --out-dir=/root/rml24_gs_single_direct_$(date +%s)
#   # dual-SDR dc-transport, diagnostic bypass OFF (pure production baseline)
#   bash scripts/run_radioml_gate_separation.sh \
#       --sdr=dual --mode=short24 --adaptation=dc-transport \
#       --input-dir=<DC tx payload pkg> \
#       --tx-control=tcp://<PC_IP>:39010 \
#       --rx-uri="<board RX SDR URI>" \
#       --out-dir=/root/rml24_gs_dual_dc_$(date +%s)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Frozen 24-class BF16 model identity (NOT the 23-class ZG default in common_rml23.sh).
MODEL_JSON="$ROOT/model_rml24_bf16/rml24_adamrv11_bf16.json"
MODEL_RAW="$ROOT/model_rml24_bf16/rml24_adamrv11_bf16.raw"
MODEL_JSON_SHA="28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
MODEL_RAW_SHA="c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
PHASE_SINGLE="radioml-original-singlesdr-ab-24class-bf16-fix10"
PHASE_DUAL="radioml-original-dualsdr-ab-24class-bf16-fix10"

# Frozen RF contract (red lines; runner defaults + readback).
CENTER_HZ=2400000000
SAMPLE_RATE=2560000
RX_GAIN_DB=35.0
RX_BW=18000000
TX_BW=18000000
TX_ATTEN_DB=-40.0
TARGET_RMS=2048.0
RF_PATH="direct-cable"

SDR=""
MODE=""
ADAPTATION=""
INPUT_DIR=""
TX_CONTROL=""
RX_URI=""
OUT_DIR=""
DIAG_FLAG=""

usage() {
    echo "Usage: $0 --sdr=single|dual --mode=short24|full480 --adaptation=direct|dc-transport [--diagnostic-force-classify] --input-dir=<tx payload pkg> [--tx-control=tcp://<PC_IP>:39010 (dual only)] --rx-uri=<SDR uri> --out-dir=<fresh dir>" >&2
    exit 2
}
for arg in "$@"; do
    case "$arg" in
        --sdr=*)         SDR="${arg#--sdr=}" ;;
        --mode=*)        MODE="${arg#--mode=}" ;;
        --adaptation=*)  ADAPTATION="${arg#--adaptation=}" ;;
        --input-dir=*)   INPUT_DIR="${arg#--input-dir=}" ;;
        --tx-control=*)  TX_CONTROL="${arg#--tx-control=}" ;;
        --rx-uri=*)      RX_URI="${arg#--rx-uri=}" ;;
        --out-dir=*)     OUT_DIR="${arg#--out-dir=}" ;;
        --diagnostic-force-classify) DIAG_FLAG="--diagnostic-force-classify" ;;
        *) echo "ERROR: unknown arg: $arg" >&2; usage ;;
    esac
done

# ---- fail-closed validation ------------------------------------------------
[ -n "$SDR" ] || { echo "ERROR: --sdr=single|dual required" >&2; usage; }
[ "$SDR" = "single" ] || [ "$SDR" = "dual" ] || {
    echo "ERROR: --sdr must be single or dual (got '$SDR')" >&2; exit 2; }
[ -n "$MODE" ] || { echo "ERROR: --mode=short24|full480 required" >&2; usage; }
[ "$MODE" = "short24" ] || [ "$MODE" = "full480" ] || {
    echo "ERROR: --mode must be short24 or full480 (got '$MODE')" >&2; exit 2; }
[ -n "$ADAPTATION" ] || { echo "ERROR: --adaptation=direct|dc-transport required" >&2; usage; }
[ "$ADAPTATION" = "direct" ] || [ "$ADAPTATION" = "dc-transport" ] || {
    echo "ERROR: --adaptation must be direct or dc-transport (got '$ADAPTATION')" >&2; exit 2; }
[ -n "$INPUT_DIR" ] || { echo "ERROR: --input-dir=<tx payload package dir> required" >&2; usage; }
[ -f "$INPUT_DIR/tx_manifest.tsv" ] || {
    echo "ERROR: tx_manifest.tsv not found in input dir: $INPUT_DIR" >&2; exit 2; }
[ -n "$RX_URI" ] || { echo "ERROR: --rx-uri=<SDR uri> required" >&2; usage; }
[ -n "$OUT_DIR" ] || { echo "ERROR: --out-dir=<fresh dir> required" >&2; usage; }
[ -e "$OUT_DIR" ] && {
    echo "ERROR: output dir already exists (refuse overwrite): $OUT_DIR" >&2; exit 2; }
[ -f "$MODEL_JSON" ] && [ -f "$MODEL_RAW" ] || {
    echo "ERROR: frozen 24-class BF16 model artifacts missing under model_rml24_bf16/" >&2
    exit 2; }

if [ "$SDR" = "dual" ]; then
    [ -n "$TX_CONTROL" ] || {
        echo "ERROR: --tx-control=tcp://<PC_IP>:39010 required for dual-SDR" >&2; usage; }
    [ -f "$INPUT_DIR/route_d2_rf_manifest.tsv" ] || {
        echo "ERROR: route_d2_rf_manifest.tsv not found in input dir (run pc_tx_radioml_dualsdr.py build-frozen-dir): $INPUT_DIR" >&2; exit 2; }
    PHASE="$PHASE_DUAL"
else
    PHASE="$PHASE_SINGLE"
fi

# ---- manifest adaptation tag vs --adaptation (fail-closed, mirrors the loader) ----
if [ "$ADAPTATION" = "direct" ]; then
    expect_cols=18; expect_tag="cyclic_tile_1024_to_53760_rms2048_ci16"
else
    expect_cols=22; expect_tag="dc_transport_cyclic_tile_1024_to_53760_rms2048_ci16"
fi
mcols="$(head -n 1 "$INPUT_DIR/tx_manifest.tsv" | awk -F'\t' '{print NF}')"
[ "$mcols" = "$expect_cols" ] || {
    echo "ERROR: tx_manifest.tsv is ${mcols}-col but --adaptation=$ADAPTATION expects ${expect_cols}-col." >&2
    exit 2; }
bad_tag="$(awk -F'\t' 'NR>1 && $18 != "'"$expect_tag"'" {print NR; exit}' "$INPUT_DIR/tx_manifest.tsv")"
[ -z "$bad_tag" ] || {
    echo "ERROR: tx_manifest.tsv line $bad_tag has adaptation tag != $expect_tag." >&2
    exit 2; }

LOG="${OUT_DIR}.run.log"

echo "RADIOML_GATE_SEPARATION_START sdr=$SDR mode=$MODE adaptation=$ADAPTATION diagnostic_force_classify=${DIAG_FLAG:+ON}${DIAG_FLAG:-OFF} input_dir=$INPUT_DIR rx_uri=$RX_URI out_dir=$OUT_DIR model_sha=$MODEL_RAW_SHA"
if [ "$SDR" = "dual" ]; then
    echo "RADIOML_GATE_SEPARATION_SAFETY dual_sdr_rx_only_board_no_tx rf_path=$RF_PATH center=$CENTER_HZ sample_rate=$SAMPLE_RATE rx_gain=$RX_GAIN_DB rx_bw=$RX_BW target_rms=$TARGET_RMS tx_control=$TX_CONTROL"
else
    echo "RADIOML_GATE_SEPARATION_SAFETY single_sdr_local_tx_no_pc_tx rf_path=$RF_PATH center=$CENTER_HZ sample_rate=$SAMPLE_RATE rx_gain=$RX_GAIN_DB rx_bw=$RX_BW tx_bw=$TX_BW tx_atten=$TX_ATTEN_DB target_rms=$TARGET_RMS"
fi

js="$(sha256sum "$MODEL_JSON" | awk '{print $1}')"
rs="$(sha256sum "$MODEL_RAW"  | awk '{print $1}')"
[ "$js" = "$MODEL_JSON_SHA" ] || { echo "ERROR: model JSON SHA mismatch: $js" >&2; exit 2; }
[ "$rs" = "$MODEL_RAW_SHA"  ] || { echo "ERROR: model RAW SHA mismatch: $rs" >&2; exit 2; }
echo "RADIOML_GATE_SEPARATION_MODEL_SHA_OK"

# ---- integration gate: the phase must be present in gate9_phase.hpp ----
if ! grep -q "$PHASE" "$ROOT/board_package/gate9_phase.hpp" 2>/dev/null; then
    echo "ERROR: board producer phase '$PHASE' NOT in board_package/gate9_phase.hpp." >&2
    echo "       Apply the dc-ab1 integrated PATCH first (single/dual phase + runner + dispatch)." >&2
    exit 2
fi

ARGS=( --phase="$PHASE" --model-json="$MODEL_JSON" --model-raw="$MODEL_RAW" \
       --model-sha="$MODEL_RAW_SHA" --mode="$MODE" --adaptation="$ADAPTATION" \
       --input-dir="$INPUT_DIR" --rx-uri="$RX_URI" --center="$CENTER_HZ" \
       --sample-rate="$SAMPLE_RATE" --rx-gain="$RX_GAIN_DB" --rx-bw="$RX_BW" \
       --rf-tx-target-rms="$TARGET_RMS" --rf-path="$RF_PATH" --out-dir="$OUT_DIR" )
if [ "$SDR" = "dual" ]; then
    ARGS+=( --tx-control="$TX_CONTROL" )
else
    ARGS+=( --tx-bw="$TX_BW" --tx-atten="$TX_ATTEN_DB" )
fi
if [ -n "$DIAG_FLAG" ]; then
    ARGS+=( "$DIAG_FLAG" )
fi

set +e
bash "$ROOT/scripts/run_gate9_rml23.sh" "${ARGS[@]}" 2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
set -e

if [ -d "$OUT_DIR" ]; then
    mv "$LOG" "$OUT_DIR/run.log"
    echo "RADIOML_GATE_SEPARATION_END rc=$rc out_dir=$OUT_DIR run.log moved into out_dir"
else
    echo "RADIOML_GATE_SEPARATION_END rc=$rc out_dir=$OUT_DIR (runner failed before mkdir; log left at $LOG)"
fi

echo "Next (host, after copying the whole \$OUT_DIR back):"
echo "  python -I scripts/judge_radioml_gate_separation.py \\"
echo "      --input-package <npu-ab1 input_package> \\"
echo "      --board-<single|dual>-<direct|dc> <board_results.tsv> \\"
echo "      --diag-<single|dual>-<direct|dc> <board_diagnostic_results.tsv> \\"
echo "      [--blind-<single|dual>-<direct|dc> <blind board_results.tsv>] \\"
echo "      --out-dir <fresh judge dir>"

exit $rc
