#!/usr/bin/env bash
# run_no_signal_ambient.sh -- 新增项2: the real no-signal integration test
# (Gate 9 --phase=ambient, rx-only).
#
# Runs the Gate 9 producer in the ambient phase: NO TX buffer is ever created
# (tx_active=0), the receiver listens continuously on the EXTERNAL RF input
# (loopback=0), and the full SDR -> DSP -> SignalPresence -> UI chain runs per
# frame.  A NO_SIGNAL / ACQUIRING / SIGNAL_LOST / INVALID frame NEVER publishes a
# classification (argmax_idx=-1); a real signal injected / removed transitions
# SIGNAL_PRESENT <-> NO_SIGNAL through the hysteresis + consecutive-frame
# confirmation, logged as PRESENCE_TRANSITION lines.
#
#   ./run_no_signal_ambient.sh                      # 64 frames, rx-only
#   ./run_no_signal_ambient.sh --frames=200         # longer observation window
#   ./run_no_signal_ambient.sh --rec-scale=4.096    # calibrated receiver_scale
#                                                   # (needed for correct classif.,
#                                                   # not for presence detection)
#
# To exercise the transitions (req. 3), while it runs inject a signal source (a
# second Pluto TX, or a generator), remove it, then inject it again; watch the
# PRESENCE_TRANSITION lines and the final presence_transitions= / nosignal= /
# present= summary in the GATE_RESULT detail.
#
# Exit code: the binary's own (0/1/2 = pass / fail / device-not-found).  The gate
# PASS is deterministic in any lab: frames==--frames, every frame valid, no fake
# classification on a non-present frame, no stream anomaly, restore ok, control ok.
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$(require_bin board_gate9_full_chain_12class)"
require_libiio_runtime
banner "Gate 9: no-signal ambient (rx-only, tx_active=0)"

exec "$BIN" \
    --model-json="$MODEL_JSON" \
    --model-raw="$MODEL_RAW" \
    --model-sha="$MODEL_RAW_SHA" \
    --phase=ambient \
    --frames=64 \
    --rx-gain=10 \
    --rec-scale=1.0 \
    "$@"
