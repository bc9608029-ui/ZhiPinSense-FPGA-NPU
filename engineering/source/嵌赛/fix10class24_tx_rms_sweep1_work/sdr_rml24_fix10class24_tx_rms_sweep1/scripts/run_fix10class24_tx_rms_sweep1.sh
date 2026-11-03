#!/usr/bin/env bash
# run_fix10class24_tx_rms_sweep1.sh -- fix10class24-tx-rms-sweep1 (task 39e5)
# SINGLE/DUAL-SDR TX digital RMS working-point sweep: --rf-tx-target-rms in
# {2048 (baseline), 1536 (-25%), 1024 (-50%)}, BF16 model ONLY (no TF32; the
# combination is deferred until both tasks finish).  This script is ORCHESTRATION
# ONLY: it reuses the existing single-SDR and dual-SDR 24-class runners verbatim
# (Phase A confirmed the --rf-tx-target-rms entry is already complete in both), so
# the runner's behaviour is untouched.
#
# It is a MEASUREMENT, never a regression PASS.  Forbidden tokens it must never
# print: RF_PASS, SMOKE_PASS, PROJECT_COMPLETE, FINAL_*, NEW_PRODUCTION_TARGET_RMS.
# Forbidden config: RMS > 2048, TX attenuation above -40 dB (hard ceiling), and
# raising RF power.
#
# Usage (run on the board from the package root):
#   # single SDR, baseline RMS, first round:
#   bash scripts/run_fix10class24_tx_rms_sweep1.sh --link=single --rx-uri=usb:1.3.5 \
#       --mode=short2 --target-rms=2048 --out-root=/tmp/rms_sweep --run=1
#   # dual SDR (PC owns TX; board owns RX):
#   bash scripts/run_fix10class24_tx_rms_sweep1.sh --link=dual --rx-uri=usb:1.3.5 \
#       --tx-control=tcp://192.168.126.10:39010 --mode=full24 --target-rms=1536 \
#       --out-root=/tmp/rms_sweep --run=1
#
# Fail-closed rules enforced here (before any runner is launched):
#   * --target-rms must be exactly one of 2048 / 1536 / 1024 (reject 2049/0/neg/str).
#   * TX attenuation is FIXED at -40 dB (never raised; runner refuses > -40 too).
#   * output run dir must NOT already exist (refuse overwrite).
#   * single link: no --tx-control (PC TX service must NOT be used).
#   * dual   link: --tx-control required (PC TX address must be given).
#   * dual   link: the PC TX command printed below uses the SAME --target-rms; the
#     dual-SDR PREPARE/READY handshake already fail-closes on any PC-vs-board
#     payload_sha_post / tx_scale mismatch, so a wrong PC RMS cannot classify.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ---------------------------------------------------------------------------
# Frozen board configuration (mirrors the production 24-class dual/single-SDR
# commands).  The model is the 24-class BF16 model (NOT the 23-class ZG model).
# ---------------------------------------------------------------------------
MODEL_JSON="model_rml24_bf16/rml24_adamrv11_bf16.json"
MODEL_RAW="model_rml24_bf16/rml24_adamrv11_bf16.raw"
MODEL_RAW_SHA="c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
FROZEN_DIR="clean24_smoke"
BASELINE="baselines/clean24_smoke_raw24_bf16_baseline.tsv"

CENTER_HZ="2400000000"
SAMPLE_RATE=2560000
RX_GAIN=35
RX_BW=18000000
TX_BW=18000000
TX_ATTEN=-40              # the -40 dB safety ceiling (runner refuses anything above)
DIAGNOSTIC_CLASSES="BPSK,4ASK"

# ---- operator-facing args (all validated fail-closed below) ----------------
LINK=""
RX_URI=""
TX_CONTROL=""
MODE="full24"
TARGET_RMS=""
OUT_ROOT=""
RUN=1

usage() {
    echo "Usage: $0 --link=single|dual --rx-uri=<URI> [--tx-control=<tcp://IP:39010>]" >&2
    echo "       --mode=short2|full24 --target-rms=2048|1536|1024 --out-root=<DIR> [--run=1|2|3]" >&2
    exit 2
}

for arg in "$@"; do
    case "$arg" in
        --link=*)       LINK="${arg#--link=}" ;;
        --rx-uri=*)     RX_URI="${arg#--rx-uri=}" ;;
        --tx-control=*) TX_CONTROL="${arg#--tx-control=}" ;;
        --mode=*)       MODE="${arg#--mode=}" ;;
        --target-rms=*) TARGET_RMS="${arg#--target-rms=}" ;;
        --out-root=*)   OUT_ROOT="${arg#--out-root=}" ;;
        --run=*)        RUN="${arg#--run=}" ;;
        *) echo "ERROR: unknown arg: $arg" >&2; usage ;;
    esac
done

# ---- fail-closed validation -------------------------------------------------
case "$LINK" in
    single|dual) ;;
    *) echo "ERROR: --link must be single or dual (got '$LINK')." >&2; usage ;;
esac
if [ -z "$RX_URI" ]; then
    echo "ERROR: --rx-uri=<URI> is required." >&2; usage
fi
case "$MODE" in
    short2|full24) ;;
    *) echo "ERROR: --mode must be short2 or full24 (got '$MODE')." >&2; usage ;;
esac
case "$TARGET_RMS" in
    2048|1536|1024) ;;
    *) echo "ERROR: --target-rms must be exactly one of 2048/1536/1024 (got '$TARGET_RMS')." >&2
       echo "       RMS > 2048 or any non-listed value is FORBIDDEN." >&2; usage ;;
esac
if [ -z "$OUT_ROOT" ]; then
    echo "ERROR: --out-root=<DIR> is required." >&2; usage
fi
case "$RUN" in
    1|2|3) ;;
    *) echo "ERROR: --run must be 1, 2 or 3 (got '$RUN')." >&2; usage ;;
esac
if [ "$LINK" = "single" ] && [ -n "$TX_CONTROL" ]; then
    echo "ERROR: single link must NOT use a PC TX service (--tx-control forbidden)." >&2
    echo "       The single SDR drives BOTH TX and RX locally over the coax." >&2
    exit 2
fi
if [ "$LINK" = "dual" ] && [ -z "$TX_CONTROL" ]; then
    echo "ERROR: dual link requires --tx-control=<tcp://IP:39010> (PC TX address)." >&2
    exit 2
fi

RUN_DIR="$OUT_ROOT/${LINK}_bf16_rms${TARGET_RMS}_run${RUN}"
if [ -e "$RUN_DIR" ]; then
    echo "ERROR: output run dir already exists (refuse overwrite): $RUN_DIR" >&2
    exit 2
fi
mkdir -p "$RUN_DIR"

# ---- PC TX service command (dual only; SAME RMS as the board) ---------------
pc_tx_command() {
    cat <<EOF
PC TX service (run on the Windows PC BEFORE this dual-SDR round, e.g. PowerShell):
  & 'D:\\radioconda\\python.exe' -I 'host_tools\\pc_tx_sdr_fix10.py' `
    --listen '0.0.0.0:39010' `
    --tx-uri <TX_SDR_URI> `
    --frozen-dir 'clean24_smoke' `
    --input-kind 'radioml-d2-2p56m' `
    --center 2400000000 --sample-rate 2560000 --tx-bw 18000000 `
    --tx-atten -40 `
    --rf-path 'direct-cable' `
    --rf-tx-target-rms ${TARGET_RMS}
Wait for "listening on 0.0.0.0:39010".  NOTE: --rf-tx-target-rms MUST be ${TARGET_RMS}
(identical to this board round); the PREPARE/READY handshake fail-closes on any mismatch.
EOF
}

# ---- config metadata (recorded into the run dir before launch) --------------
write_meta() {
    {
        echo "FIX10CLASS24_TX_RMS_SWEEP1_CONFIG link=$LINK mode=$MODE"
        echo "FIX10CLASS24_TX_RMS_SWEEP1_CONFIG requested_target_rms=$TARGET_RMS run=$RUN"
        echo "FIX10CLASS24_TX_RMS_SWEEP1_CONFIG model_json=$MODEL_JSON model_raw_sha=$MODEL_RAW_SHA"
        echo "FIX10CLASS24_TX_RMS_SWEEP1_CONFIG tx_atten=$TX_ATTEN rx_gain=$RX_GAIN rx_bw=$RX_BW tx_bw=$TX_BW"
        echo "FIX10CLASS24_TX_RMS_SWEEP1_CONFIG center_hz=$CENTER_HZ sample_rate=$SAMPLE_RATE"
        echo "FIX10CLASS24_TX_RMS_SWEEP1_CONFIG link_type=${LINK}_sdr tx_scale=deterministic(target_rms/native_rms; runner-internal; dual-SDR handshake cross-checked)"
        echo "FIX10CLASS24_TX_RMS_SWEEP1_CONFIG out_dir=$RUN_DIR"
    } > "$RUN_DIR/config.meta"
    echo "FIX10CLASS24_TX_RMS_SWEEP1_START link=$LINK mode=$MODE requested_target_rms=$TARGET_RMS run=$RUN out_dir=$RUN_DIR"
    echo "FIX10CLASS24_TX_RMS_SWEEP1_SAFETY tx_atten=$TX_ATTEN rms_ceil=2048 forbidden_verdict_tokens_enforced=1"
}

if [ "$LINK" = "dual" ]; then
    echo "===================================================================="
    echo "START_PC_TX_AND_WAIT_FOR_LISTENING link=dual requested_target_rms=$TARGET_RMS run=$RUN"
    echo "  TX attenuation FIXED at -40 dB (hard safety ceiling)."
    echo "===================================================================="
    pc_tx_command
    if [ "${SWEEP_NO_PROMPT:-0}" = "1" ]; then
        echo "(SWEEP_NO_PROMPT=1: not waiting for Enter)"
    else
        read -r -p "Press Enter once the PC reports 'listening on 0.0.0.0:39010'... "
    fi
fi

write_meta

# ---- build the runner args (verbatim per link, only --rf-tx-target-rms varies) ----
COMMON_ARGS=(
    --model-json="$MODEL_JSON"
    --model-raw="$MODEL_RAW"
    --model-sha="$MODEL_RAW_SHA"
    --frozen-dir="$FROZEN_DIR"
    --baseline="$BASELINE"
    --input-kind=radioml-d2-2p56m
    --center="$CENTER_HZ"
    --rx-bw="$RX_BW"
    --rx-gain="$RX_GAIN"
    --tx-atten="$TX_ATTEN"
    --rf-tx-target-rms="$TARGET_RMS"
    --rf-path=direct-cable
    --diagnostic-classes="$DIAGNOSTIC_CLASSES"
    --diagnostic-per-class=1
    --dump-failed-rx
    --dump-recovery-diagnostics
    --out-dir="$RUN_DIR"
)

if [ "$LINK" = "single" ]; then
    RUNNER_ARGS=(
        --phase=iq-rf-loopback-24class-bf16-fix10
        --rx-uri="$RX_URI"
        --mode="$MODE"
        --sample-rate="$SAMPLE_RATE"
        --tx-bw="$TX_BW"
    )
else
    RUNNER_ARGS=(
        --phase=iq-pc-tx-board-rx-24class-bf16-fix10
        --rx-uri="$RX_URI"
        --tx-control="$TX_CONTROL"
    )
fi

set +e
bash "$ROOT/scripts/run_gate9_rml23.sh" \
    "${RUNNER_ARGS[@]}" "${COMMON_ARGS[@]}" \
    2>&1 | tee "$RUN_DIR/run.log"
rc=${PIPESTATUS[0]}
set -e

echo "FIX10CLASS24_TX_RMS_SWEEP1_END link=$LINK requested_target_rms=$TARGET_RMS run=$RUN rc=$rc out_dir=$RUN_DIR"
echo "Next (host):"
echo "  python3 scripts/audit_fix10class24_tx_rms_sweep1.py --sweep-root '$OUT_ROOT' [--link single|dual] \\"
echo "      --clean24-dir '$FROZEN_DIR' --icraft-run /path/to/icraft-run.exe"

exit $rc
