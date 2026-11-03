#!/usr/bin/env bash
# run_gate10.sh -- Gate 10: twelve-class RF SELF-TEST.
#
# For each modulation class the board synthesises a deterministic 128 kS/s
# waveform, upsamples it x20, transmits it through PlutoTX, captures it back
# through the SDR->tensor preprocess chain, and classifies every frame with the
# NPU.  PASS requires EVERY tested class to reach --min-match-rate with no stream
# anomaly and a successful device restore.  See
# board_gate10_selftest_12class.cpp and docs/RF_SELF_TEST_CONTRACT.md.
#
#   ./run_gate10.sh                              # all 12 classes, digital loopback
#   ./run_gate10.sh --class=6                    # BPSK only (bring-up)
#   ./run_gate10.sh --loopback=rf --confirm-safe-rf-path --tx-atten=-40 \
#                   --center=2450000000          # external RF path (real RF TX!)
#
# Digital loopback emits nothing externally and is the default.  An external-RF
# path (--loopback=rf) is REFUSED by the gate unless --confirm-safe-rf-path is
# given, and you MUST also raise --tx-atten off the -89.75 dB safety floor (never
# above -40 dB) so the receiver actually sees the self-test signal.
#
# Exit code: the binary's own (0/1/2 = pass / fail / device-not-found).
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$(require_bin board_gate10_selftest_12class)"
require_libiio_runtime
banner "Gate 10: twelve-class RF self-test"

exec "$BIN" \
    --model-json="$MODEL_JSON" \
    --model-raw="$MODEL_RAW" \
    --model-sha="$MODEL_RAW_SHA" \
    --frames=20 \
    --tx-frames=64 \
    --settle-frames=2 \
    --settle-wait-ms=100 \
    --min-match-rate=0.90 \
    --peak-limit=1638 \
    --rx-gain=10 \
    --loopback=digital \
    --seed=0x39e50001 \
    --center=2450000000 \
    "$@"
