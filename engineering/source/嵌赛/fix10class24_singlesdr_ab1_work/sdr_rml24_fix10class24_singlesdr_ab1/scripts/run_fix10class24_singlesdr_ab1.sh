#!/usr/bin/env bash
# run_fix10class24_singlesdr_ab1.sh -- fix10class24-singlesdr-ab1 (task book 39e5)
# SINGLE-SDR 24-class BF16 self-loopback A/B run (one Pluto does BOTH the local TX and
# the RX over the external 50-ohm coax, loopback=0, shared clock/LO).
#
# This is the strict A/B control for the dual-SDR 18/24 result: the recovery chain is
# byte-for-byte the dual-SDR rxrecovery1 runner (coarse-CFO + fractional timing +
# wide-linear compensation + bounded recapture <= 3 + final-capture selection), and the
# ONLY difference is the topology swap (two SDRs -> one SDR, PC TX over TCP -> local
# cyclic transmit).  There is no PC-TX control channel or TCP command socket anywhere
# here.
#
# It is a MEASUREMENT, never a regression PASS.  The runner reports three of the four
# A/B metrics directly (coverage / gated_accuracy / end_to_end_accuracy) and prints
# forced_raw24_accuracy=PENDING; the fourth metric is completed offline by
# scripts/aggregate_fix10class24_singlesdr_ab1_forced.py as
# HYBRID_BOARD_GATED_PLUS_HOST_FORCED (see the hint printed at the end).
#
# Usage (run on the board from the package root):
#   # short smoke (BPSK + 4ASK) first:
#   bash scripts/run_fix10class24_singlesdr_ab1.sh --rx-uri=usb:1.3.5 --mode=short2
#   # full 24-class run:
#   bash scripts/run_fix10class24_singlesdr_ab1.sh --rx-uri=usb:1.3.5 --mode=full24
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

CENTER_HZ="2400000000"
SAMPLE_RATE=2560000          # MUST equal iqdloop::kFrozenFsIn (runner enforces)
RX_GAIN=35
RX_BW=18000000
TX_BW=18000000
TX_ATTEN=-40                 # the -40 dB safety ceiling (runner refuses anything above)
RF_TX_TARGET_RMS=2048

# ---- parse (only these three are operator-facing) --------------------------
RX_URI=""
MODE="full24"
OUT_DIR=""
for arg in "$@"; do
    case "$arg" in
        --rx-uri=*)  RX_URI="${arg#--rx-uri=}" ;;
        --mode=*)    MODE="${arg#--mode=}" ;;
        --out-dir=*) OUT_DIR="${arg#--out-dir=}" ;;
        --center=*)  CENTER_HZ="${arg#--center=}" ;;
        *) echo "ERROR: unknown arg: $arg" >&2; exit 2 ;;
    esac
done

if [ -z "$RX_URI" ]; then
    echo "ERROR: --rx-uri=<URI> is required (the single SDR drives BOTH TX and RX)." >&2
    echo "Usage: $0 --rx-uri=usb:1.3.5 [--mode=short2|full24] [--out-dir=/root/...]" >&2
    exit 2
fi
if [ "$MODE" != "short2" ] && [ "$MODE" != "full24" ]; then
    echo "ERROR: --mode must be short2 or full24 (got '$MODE')." >&2
    exit 2
fi

if [ -z "$OUT_DIR" ]; then
    OUT_DIR="/tmp/rml24_singlesdr_ab1_${MODE}_$(date +%s)"
fi
mkdir -p "$OUT_DIR"

echo "FIX10CLASS24_SINGLESDR_AB1_START mode=$MODE rx_uri=$RX_URI center=$CENTER_HZ out_dir=$OUT_DIR"

set +e
bash "$ROOT/scripts/run_gate9_rml23.sh" \
    --phase=iq-rf-loopback-24class-bf16-fix10 \
    --model-json="$MODEL_JSON" \
    --model-raw="$MODEL_RAW" \
    --model-sha="$MODEL_SHA" \
    --rx-uri="$RX_URI" \
    --mode="$MODE" \
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
    --dump-failed-rx \
    --dump-recovery-diagnostics \
    --out-dir="$OUT_DIR" \
    2>&1 | tee "$OUT_DIR/run.log"
rc=${PIPESTATUS[0]}
set -e

echo "FIX10CLASS24_SINGLESDR_AB1_END mode=$MODE rc=$rc out_dir=$OUT_DIR"
echo "forced_raw24_accuracy=PENDING on the board; complete it offline (host, icraft-run.exe):"
echo "  python3 scripts/aggregate_fix10class24_singlesdr_ab1_forced.py --phase aggregate \\"
echo "      --out-dir '$OUT_DIR' --clean24-dir '$FROZEN_DIR' --baseline '$BASELINE' \\"
echo "      --icraft-run /path/to/icraft-run.exe --model-dir model_rml24_bf16 \\"
echo "      --force-classify-tool host_tools/replay_fix10class24_failed_rx_force_classify.sh"

exit $rc
