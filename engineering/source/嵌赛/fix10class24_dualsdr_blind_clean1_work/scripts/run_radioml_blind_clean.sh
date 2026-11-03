#!/usr/bin/env bash
# run_radioml_blind_clean.sh -- board-side BLIND pure-modulation dual-SDR measurement
# (fix10class24-dualsdr-blind-clean1, phase iq-blind-rx-24class-bf16-fix10).
#
# The Windows PC owns the TX SDR and CYCLICALLY transmits a PURE-modulated 24-class
# RadioML2018.01A clean waveform (NO training frame / preamble / tail) over 50-ohm
# coax; this board owns the RX SDR and classifies it with ONLY the received IQ + the
# frozen BF16 model + a frozen reconstruction scale + a frozen window rule.  The board
# NEVER sees the transmitted sample, its DC/scale, its correct window, or its label.
#
# Board = RX-only and is the control-channel CLIENT; it connects to the PC TX service
# (SERVER, port 39010).  On the PC you must FIRST launch the blind TX service:
#   D:\radioconda\python.exe -I host_tools/pc_tx_blind_clean.py \
#       --listen 0.0.0.0:39010 --tx-uri "<PC_TX_URI>" --tx-dir "<blind tx package>"
#
# This is a MEASUREMENT, never a regression PASS.  Forbidden tokens this script must
# never print on its own: RF_PASS, SMOKE_PASS, PROJECT_COMPLETE, FINAL_*, HOST_MATCH
# (the host judger owns those verdicts).  The board NEVER forces a classification.
#
# --rx-gain=35 is passed EXPLICITLY: run_gate9_rml23.sh defaults --rx-gain=10 and the
# runner resolves the LAST occurrence, so omitting it here would silently run at 10 dB.
# --sample-rate=2560000 and --measurements=25 are also passed explicitly (the blind
# runner refuses any other value).
#
# Usage (run on the board, from the project root):
#   bash scripts/run_radioml_blind_clean.sh \
#       --tx-control=tcp://<PC_IP>:39010 \
#       --rx-uri="<board RX SDR URI>" \
#       --out-dir=/root/rml24_blind_clean_$(date +%s)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Frozen 24-class BF16 model identity (NOT the 23-class ZG default in common_rml23.sh).
MODEL_JSON="$ROOT/model_rml24_bf16/rml24_adamrv11_bf16.json"
MODEL_RAW="$ROOT/model_rml24_bf16/rml24_adamrv11_bf16.raw"
MODEL_JSON_SHA="28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
MODEL_RAW_SHA="c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
PHASE="iq-blind-rx-24class-bf16-fix10"

# Frozen blind RF contract (red lines; the runner defaults + readback).  The board
# owns NO TX: TX config (bw/atten/cyclic payload) belongs to the PC TX service.
CENTER_HZ=2400000000
SAMPLE_RATE=2560000
RX_GAIN_DB=35.0
RX_BW=18000000
MEASUREMENTS=25
RF_PATH="direct-cable"

TX_CONTROL=""
RX_URI=""
OUT_DIR=""

usage() {
    echo "Usage: $0 --tx-control=tcp://<PC_IP>:39010 --rx-uri=<SDR uri> --out-dir=<fresh dir>" >&2
    exit 2
}
for arg in "$@"; do
    case "$arg" in
        --tx-control=*) TX_CONTROL="${arg#--tx-control=}" ;;
        --rx-uri=*)     RX_URI="${arg#--rx-uri=}" ;;
        --out-dir=*)    OUT_DIR="${arg#--out-dir=}" ;;
        *) echo "ERROR: unknown arg: $arg" >&2; usage ;;
    esac
done

# ---- fail-closed validation (mirrors the runner's own checks) --------------
[ -n "$TX_CONTROL" ] || { echo "ERROR: --tx-control=tcp://<PC_IP>:39010 required" >&2; usage; }
[ -n "$RX_URI" ] || { echo "ERROR: --rx-uri=<board RX SDR URI> required" >&2; usage; }
[ -n "$OUT_DIR" ] || { echo "ERROR: --out-dir=<fresh dir> required" >&2; usage; }
[ -e "$OUT_DIR" ] && {
    echo "ERROR: output dir already exists (refuse overwrite): $OUT_DIR" >&2
    echo "       Use a fresh timestamped dir, e.g. /root/rml24_blind_clean_\$(date +%s)." >&2
    exit 2; }
[ -f "$MODEL_JSON" ] && [ -f "$MODEL_RAW" ] || {
    echo "ERROR: frozen 24-class BF16 model artifacts missing under model_rml24_bf16/" >&2
    exit 2; }

# ---- transcript (sibling of $OUT_DIR; moved inside after the runner creates it) ----
LOG="${OUT_DIR}.run.log"

echo "RADIOML_BLIND_CLEAN_START tx_control=$TX_CONTROL rx_uri=$RX_URI out_dir=$OUT_DIR model_sha=$MODEL_RAW_SHA"
echo "RADIOML_BLIND_CLEAN_SAFETY blind_no_sample_prior board_rx_only_no_tx rf_path=$RF_PATH center=$CENTER_HZ sample_rate=$SAMPLE_RATE rx_gain=$RX_GAIN_DB rx_bw=$RX_BW measurements=$MEASUREMENTS"
echo "RADIOML_BLIND_CLEAN_PC_TX_HINT: on the PC, launch host_tools/pc_tx_blind_clean.py --tx-dir <blind tx package> --tx-uri <PC_TX_URI>"

js="$(sha256sum "$MODEL_JSON" | awk '{print $1}')"
rs="$(sha256sum "$MODEL_RAW"  | awk '{print $1}')"
[ "$js" = "$MODEL_JSON_SHA" ] || { echo "ERROR: model JSON SHA mismatch: $js" >&2; exit 2; }
[ "$rs" = "$MODEL_RAW_SHA"  ] || { echo "ERROR: model RAW SHA mismatch: $rs" >&2; exit 2; }
echo "RADIOML_BLIND_CLEAN_MODEL_SHA_OK"

# ---- integration gate: the phase must be present in gate9_phase.hpp ----
if ! grep -q "$PHASE" "$ROOT/board_package/gate9_phase.hpp" 2>/dev/null; then
    echo "ERROR: board producer phase '$PHASE' NOT in board_package/gate9_phase.hpp." >&2
    echo "       Apply the blind-clean1 PATCH first (it adds the phase + runner + dispatch)." >&2
    echo "       This script will not silently run a missing phase -- exit 2." >&2
    exit 2
fi

set +e
bash "$ROOT/scripts/run_gate9_rml23.sh" \
    --phase="$PHASE" \
    --model-json="$MODEL_JSON" \
    --model-raw="$MODEL_RAW" \
    --model-sha="$MODEL_RAW_SHA" \
    --tx-control="$TX_CONTROL" \
    --rx-uri="$RX_URI" \
    --center="$CENTER_HZ" \
    --sample-rate="$SAMPLE_RATE" \
    --rx-gain="$RX_GAIN_DB" \
    --rx-bw="$RX_BW" \
    --measurements="$MEASUREMENTS" \
    --rf-path="$RF_PATH" \
    --out-dir="$OUT_DIR" \
    2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
set -e

if [ -d "$OUT_DIR" ]; then
    mv "$LOG" "$OUT_DIR/run.log"
    echo "RADIOML_BLIND_CLEAN_END rc=$rc out_dir=$OUT_DIR run.log moved into out_dir"
else
    echo "RADIOML_BLIND_CLEAN_END rc=$rc out_dir=$OUT_DIR (runner failed before mkdir; log left at $LOG)"
fi

echo "Next (host, after copying the whole \$OUT_DIR back):"
echo "  python -I scripts/judge_radioml_blind_clean.py \\"
echo "      --tx-dir <blind tx package> \\"
echo "      --board-results <copied \$OUT_DIR/board_results.tsv> \\"
echo "      --digital <digital_replay.tsv> \\"
echo "      --out-dir <fresh judge dir>"

exit $rc
