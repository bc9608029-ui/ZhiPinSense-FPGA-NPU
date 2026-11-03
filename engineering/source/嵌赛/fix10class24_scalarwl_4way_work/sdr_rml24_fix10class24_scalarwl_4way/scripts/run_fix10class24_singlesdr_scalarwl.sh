#!/usr/bin/env bash
# run_fix10class24_singlesdr_scalarwl.sh -- fix10class24-scalarwl-4way (task 39e5)
# MINIMAL single-SDR diagnostic: ONE real capture of OQPSK(source_index=11500),
# recovered with the SAME production recovery core, then BOTH model inputs (scalar +
# wide-linear) exported side-by-side and inferred by the current BF16 model on the board
# NPU.  This is a MEASUREMENT (token FIX10CLASS24_BF16_SCALARWL_DIAG), never a
# regression PASS, and never a "board accuracy": the board produces only the BF16 pair
# + the two exported inputs + a manifest; the OLD mixed-precision pair is produced
# OFFLINE on Windows (icraft-run.exe) from those same two inputs.
#
# It does NOT change the 0.100 gate, does NOT change production behaviour, and does NOT
# retrain.  The recovery chain is byte-for-byte the production
# iqdual23fix10::recover_payload_with_coarse_cfo (coarse CFO -> fractional timing ->
# three-pass estimate -> apply), and the fidelity gate is reproduced in the exact
# production branch order.
#
# Usage (run on the board from the package root):
#   bash scripts/run_fix10class24_singlesdr_scalarwl.sh --rx-uri=usb:1.3.5
#   bash scripts/run_fix10class24_singlesdr_scalarwl.sh --rx-uri=usb:1.3.5 --out-dir=/root/out
#
# Outputs (in --out-dir):
#   model_input_scalar_f32le.bin   [2,1024] fp32 scalar    model input (8192 bytes)
#   model_input_wl_f32le.bin       [2,1024] fp32 wide-linear model input (8192 bytes)
#   logits_scalar_bf16.bin         24 x fp32 (board BF16, scalar input)
#   logits_wl_bf16.bin             24 x fp32 (board BF16, wide-linear input)
#   scalarwl_diag_manifest.json    full diagnostics + the two BF16 logit vectors
#   run.log                        the board stdout (GATE_RESULT + DIAG tokens)
#
# HARD SAFETY: TX attenuation is FIXED at -40 dB (the -40 dB ceiling); the runner
# refuses any --tx-atten > -40.  The RF path is direct-cable only (no antenna, no
# amplifier).  LIBIIO_ROOT=/opt/sdr/libiio-0.26 is honoured via run_gate9_rml23.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---------------------------------------------------------------------------
# Board-specific configuration (edit once).  The model is the 24-class BF16 model,
# NOT the 23-class ZG model that common_rml23.sh defaults to; the three --model-*
# flags here override those defaults (later occurrence wins in board::get_opt).
# ---------------------------------------------------------------------------
MODEL_JSON="model_rml24_bf16/rml24_adamrv11_bf16.json"
MODEL_RAW="model_rml24_bf16/rml24_adamrv11_bf16.raw"
MODEL_SHA="c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
FROZEN_DIR="clean24_smoke"
BASELINE="baselines/clean24_smoke_raw24_bf16_baseline.tsv"

SOURCE_INDEX=11500            # OQPSK (the ONE sample this diagnostic measures)
CENTER_HZ="2400000000"
SAMPLE_RATE=2560000           # MUST equal iqdloop::kFrozenFsIn (runner enforces)
RX_GAIN=35
RX_BW=18000000
TX_BW=18000000
TX_ATTEN=-40                  # the -40 dB safety ceiling (runner refuses anything above)
RF_TX_TARGET_RMS=2048

# ---- parse (only these are operator-facing) ---------------------------------
RX_URI=""
OUT_DIR=""
for arg in "$@"; do
    case "$arg" in
        --rx-uri=*)       RX_URI="${arg#--rx-uri=}" ;;
        --source-index=*) SOURCE_INDEX="${arg#--source-index=}" ;;
        --out-dir=*)      OUT_DIR="${arg#--out-dir=}" ;;
        --center=*)       CENTER_HZ="${arg#--center=}" ;;
        *) echo "ERROR: unknown arg: $arg" >&2; exit 2 ;;
    esac
done

if [ -z "$RX_URI" ]; then
    echo "ERROR: --rx-uri=<URI> is required (the single SDR drives BOTH TX and RX)." >&2
    echo "Usage: $0 --rx-uri=usb:1.3.5 [--source-index=11500] [--out-dir=/root/...]" >&2
    exit 2
fi

if [ -z "$OUT_DIR" ]; then
    OUT_DIR="/tmp/rml24_scalarwl_$(date +%s)"
fi
mkdir -p "$OUT_DIR"

echo "FIX10CLASS24_SCALARWL_START source_index=$SOURCE_INDEX rx_uri=$RX_URI center=$CENTER_HZ out_dir=$OUT_DIR"

set +e
bash "$ROOT/scripts/run_gate9_rml23.sh" \
    --phase=iq-rf-loopback-24class-bf16-scalarwl \
    --model-json="$MODEL_JSON" \
    --model-raw="$MODEL_RAW" \
    --model-sha="$MODEL_SHA" \
    --rx-uri="$RX_URI" \
    --source-index="$SOURCE_INDEX" \
    --input-kind=radioml-d2-2p56m \
    --frozen-dir="$FROZEN_DIR" \
    --baseline="$BASELINE" \
    --center="$CENTER_HZ" \
    --sample-rate="$SAMPLE_RATE" \
    --rx-bw="$RX_BW" \
    --tx-bw="$TX_BW" \
    --rx-gain="$RX_GAIN" \
    --tx-atten="$TX_ATTEN" \
    --rf-tx-target-rms="$RF_TX_TARGET_RMS" \
    --rf-path=direct-cable \
    --out-dir="$OUT_DIR" \
    2>&1 | tee "$OUT_DIR/run.log"
rc=${PIPESTATUS[0]}
set -e

echo "FIX10CLASS24_SCALARWL_END rc=$rc out_dir=$OUT_DIR"
if [ "$rc" -eq 0 ]; then
    echo "The board produced the BF16 pair + the two model inputs + scalarwl_diag_manifest.json."
    echo "Complete the FOUR-WAY report offline on Windows (icraft-run.exe, mixed-precision model):"
    echo "  python scripts/four_way_oqpsk_scalar_wl.py --phase mixed-precision \\"
    echo "      --out-dir '$OUT_DIR' --model-dir model_rml23 \\"
    echo "      --icraft-run /path/to/icraft-run.exe"
    echo "  python scripts/four_way_oqpsk_scalar_wl.py --phase four-way --out-dir '$OUT_DIR'"
else
    echo "Diagnostic failed before completion; do not use or transfer this output directory." >&2
fi

exit $rc
