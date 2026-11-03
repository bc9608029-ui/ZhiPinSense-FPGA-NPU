#!/usr/bin/env bash
# run_fix10class24_rx_frontend_sweep.sh -- fix10class24-rxfrontend1 Phase B board
# sweep: single-variable RX-bandwidth scan (18 -> 10 -> 5 -> 3 MHz), 3 rounds each,
# with PC TX attenuation FIXED at the -40 dB safety ceiling and RX gain FIXED at 35 dB.
#
# This script controls ONLY the board RX side.  It never controls the PC TX SDR: it
# prints START_PC_TX_AND_WAIT_FOR_LISTENING before every round and blocks until the
# operator confirms the PC TX service is listening.  The PC command (always
# --tx-atten -40) is printed once, below, and must be re-run for each round.
#
# The ONLY board-side variable is --rx-bw; every other parameter is verbatim across
# all rounds.  Each round's full stdout is tee'd into
#   /tmp/rml24_rxbw_<hz>_run<1..3>_<timestamp>/run.log
# so scripts/check_fix10class24_rx_frontend_sweep.py can parse it fail-closed.
#
# HARD SAFETY: PC TX attenuation stays at -40 dB.  -35/-30 dB are REFUSED by the PC
# safety ceiling and must never appear here.  Do not modify or bypass that ceiling.
set -euo pipefail

# =============================================================================
# Board-specific configuration (edit once; values mirror the 24-class dual-SDR
# production command in M29_RML24_FIX10CLASS24_BF16_DUALSDR_AUDIT.md §9).
# =============================================================================
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_JSON="model_rml24_bf16/rml24_adamrv11_bf16.json"
MODEL_RAW="model_rml24_bf16/rml24_adamrv11_bf16.raw"
MODEL_SHA="c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
FROZEN_DIR="clean24_smoke"
BASELINE="baselines/clean24_smoke_raw24_bf16_baseline.tsv"
TX_CONTROL="tcp://192.168.126.10:39010"
RX_URI="usb:1.3.5"
CENTER_HZ="2400000000"

# ---- sweep contract (must match check_fix10class24_rx_frontend_sweep.py) ----
BANDWIDTHS_HZ=(18000000 10000000 5000000 3000000)   # widest first
ROUNDS=3
RX_GAIN_DB=35
DIAGNOSTIC_CLASSES="BPSK,4ASK"
SWEEP_ROOT="/tmp"

# =============================================================================
# PC TX service command (operator runs this on the Windows PC BEFORE each round).
# TX attenuation is FIXED at -40 dB -- the hard safety ceiling.
# =============================================================================
pc_tx_command() {
    cat <<'EOF'
PC TX service (run on the Windows PC before EACH round, e.g. PowerShell):
  $Root = 'F:\嵌赛\fix10class24_dualsdr2_work\sdr_rml24_live_board_package_pc_tx_board_rx_fix10class24_dualsdr2'
  $TxUri = 'usb:1.11.5'   # re-query with iio_info.exe -s after each replug
  Set-Location $Root
  & 'D:\radioconda\python.exe' -I 'host_tools\pc_tx_sdr_fix10.py' `
    --listen '0.0.0.0:39010' `
    --tx-uri $TxUri `
    --frozen-dir 'clean24_smoke' `
    --input-kind 'radioml-d2-2p56m' `
    --center 2400000000 `
    --sample-rate 2560000 `
    --tx-bw 18000000 `
    --tx-atten -40 `
    --rf-path 'direct-cable' `
    --rf-tx-target-rms 2048 `
    --prewarm-source-index 1500 `
    --prewarm-source-index 500
Wait for BOTH PREWARM lines and "listening on 0.0.0.0:39010".
EOF
}

prompt_pc() {
    local hz="$1" round="$2" dir="$3"
    echo
    echo "===================================================================="
    echo "START_PC_TX_AND_WAIT_FOR_LISTENING bandwidth_hz=$hz round=$round"
    echo "  round_dir=$dir"
    echo "  TX attenuation is FIXED at -40 dB (hard safety ceiling)."
    echo "===================================================================="
    pc_tx_command
    if [ "${SWEEP_NO_PROMPT:-0}" = "1" ]; then
        echo "(SWEEP_NO_PROMPT=1: not waiting for Enter)"
    else
        read -r -p "Press Enter once the PC reports 'listening on 0.0.0.0:39010'... "
    fi
}

run_round() {
    local hz="$1" round_dir="$2"
    echo "FIX10CLASS24_RX_FRONTEND_SWEEP_START bandwidth_hz=$hz rx_gain=$RX_GAIN_DB out_dir=$round_dir"
    set +e
    bash "$ROOT/scripts/run_gate9_rml23.sh" \
        --phase=iq-pc-tx-board-rx-24class-bf16-fix10 \
        --model-json="$MODEL_JSON" \
        --model-raw="$MODEL_RAW" \
        --model-sha="$MODEL_SHA" \
        --frozen-dir="$FROZEN_DIR" \
        --baseline="$BASELINE" \
        --tx-control="$TX_CONTROL" \
        --rx-uri="$RX_URI" \
        --input-kind=radioml-d2-2p56m \
        --center="$CENTER_HZ" \
        --rx-bw="$hz" \
        --rx-gain="$RX_GAIN_DB" \
        --rf-tx-target-rms=2048 \
        --rf-path=direct-cable \
        --diagnostic-classes="$DIAGNOSTIC_CLASSES" \
        --diagnostic-per-class=1 \
        --dump-failed-rx \
        --dump-recovery-diagnostics \
        --out-dir="$round_dir" \
        2>&1 | tee "$round_dir/run.log"
    local rc=${PIPESTATUS[0]}
    set -e
    echo "FIX10CLASS24_RX_FRONTEND_SWEEP_END bandwidth_hz=$hz rc=$rc out_dir=$round_dir"
}

main() {
    echo "FIX10CLASS24_RX_FRONTEND_SWEEP_PLAN bandwidths_hz=${BANDWIDTHS_HZ[*]} rounds=$ROUNDS rx_gain=$RX_GAIN_DB"
    for hz in "${BANDWIDTHS_HZ[@]}"; do
        for ((r = 1; r <= ROUNDS; r++)); do
            local ts
            ts="$(date +%s)"
            local round_dir="$SWEEP_ROOT/rml24_rxbw_${hz}_run${r}_${ts}"
            mkdir -p "$round_dir"
            prompt_pc "$hz" "$r" "$round_dir"
            run_round "$hz" "$round_dir"
        done
    done
    echo "FIX10CLASS24_RX_FRONTEND_SWEEP_DONE sweep_root=$SWEEP_ROOT"
    echo "Next: on the host run"
    echo "  python3 scripts/check_fix10class24_rx_frontend_sweep.py <sweep_root>"
}

main "$@"
