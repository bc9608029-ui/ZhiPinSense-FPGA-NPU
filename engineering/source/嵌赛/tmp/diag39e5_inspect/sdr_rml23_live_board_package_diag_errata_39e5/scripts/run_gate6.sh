#!/usr/bin/env bash
# run_gate6.sh -- Gate 6: Pluto RX -> fp32 [1,2,1024] tensor.
#
# Two modes (see board_gate6_sdr_preprocess.cpp header):
#   ./run_gate6.sh                 capture ambient RX (--loopback=0), write tensors
#   ./run_gate6.sh --loopback=1    digital loopback: TX a 10 kHz CW tone and VERIFY
#                                  every tensor still contains the tone at 128 kHz.
#
# receiver_scale (--rec-scale) is a GLOBAL fixed scalar; the Goertzel PASS criterion
# is scale-invariant, so Gate 6 does NOT depend on the calibrated value.  The §九
# calibration flow (run_calibrate_rec_scale.sh) fixes --rec-scale before Gate 9.
#
# PASS criteria (printed as GATE_RESULT by the binary, exited through unchanged):
#   frames == --frames, no stream anomaly (overflow/drop/disc/short == 0), and
#   (loopback==1) tone present in every frame (ratio_min > --ratio-min).
#
# Exit code: the binary's own (0/1/2 = pass / fail / device-not-found).
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$(require_bin board_gate6_sdr_preprocess)"
require_libiio_runtime
banner "Gate 6: SDR preprocess (Pluto RX -> tensor)"

# Defaults (override by passing --key=value flags, which are forwarded unchanged;
# a later occurrence wins, so post-script args override these defaults).
exec "$BIN" \
    --frames=16 \
    --loopback=0 \
    --tone=10000 \
    --rx-gain=10 \
    --rec-scale=1.0 \
    --ratio-min=0.3 \
    --outdir=gate6_out \
    "$@"
