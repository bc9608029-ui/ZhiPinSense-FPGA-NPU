#!/usr/bin/env bash
# run_gate9_rml23.sh -- Gate 9 RML23: the full real-time SDR -> NPU(24-class
# expA_bf16_head) -> AM-SSB merge(23-class) -> UI chain, in four phases (see
# board_gate9_full_chain_rml23.cpp header).  Built on the board-proven M22.1
# framework (run_gate9.sh); the ONLY deltas are the 24-class NPU wrapper and the
# 24->23 AM-SSB merge.
#
#   ./run_gate9_rml23.sh --phase=offline  replay golden inputs -> NPU -> merge -> UI
#                                         (strongest: proves NPU -> merge -> UI
#                                          against known inputs)
#   ./run_gate9_rml23.sh --phase=digital  Pluto digital loopback -> preprocess ->
#                                         NPU -> merge -> UI (gates CHAIN LIVENESS,
#                                         never classification)
#   ./run_gate9_rml23.sh --phase=rf       external RF loopback -- REQUIRES
#                                         --confirm-safe-rf-path (refused otherwise)
#   ./run_gate9_rml23.sh --phase=ambient  rx-only no-signal integration (no TX)
#
# For --phase=digital/rf, pass the §九-calibrated receiver_scale via --rec-scale
# (run_calibrate_rec_scale.sh), e.g.:
#   ./run_gate9_rml23.sh --phase=digital --rec-scale=4.096
# The default --rec-scale 1.0 keeps the chain running but does NOT match the
# model's RMS==1.0 input domain; it is only for mechanical smoke.
#
# For --phase=ambient (rx-only, no TX), the RF fix supports an explicit RX LO /
# RF bandwidth override plus a per-N-frame RF diagnostic summary.  The real board
# test command is:
#   ./run_gate9_rml23.sh --phase=ambient --rx-lo=2400000000 --rx-bw=200000 \
#       --rx-gain=10 --nco-offset=10000 --rf-diag --rf-diag-interval=100
# --rx-lo / --rx-bw are AMBIENT-only: when absent the old behaviour is kept; when
# present the write is read back and MUST land within tolerance (fail-closed).
# --rf-diag / --rf-diag-interval also work in --phase=digital/rf.
#
# Exit code: the binary's own (0/1/2 = pass / fail / device-not-found).
set -euo pipefail
. "$(dirname "$0")/common_rml23.sh"

BIN="$(require_bin board_gate9_full_chain_rml23)"
require_libiio_runtime
banner "Gate 9 RML23: full chain (SDR -> NPU24 -> AM-SSB merge -> 23-class UI)"

# Defaults are --key=value; a later occurrence wins, so a user's post-script args
# (e.g. --phase=digital) override these defaults.
exec "$BIN" \
    --model-json="$MODEL_JSON" \
    --model-raw="$MODEL_RAW" \
    --model-sha="$MODEL_RAW_SHA" \
    --sock="$UI_SOCK" \
    --ctl-sock="$CTL_SOCK" \
    --golden="$GOLDEN" \
    --count=240 \
    --min-match-rate=0.90 \
    --phase=offline \
    --frames=16 \
    --tone=10000 \
    --rx-gain=10 \
    --rec-scale=1.0 \
    --nco-offset=0 \
    "$@"
