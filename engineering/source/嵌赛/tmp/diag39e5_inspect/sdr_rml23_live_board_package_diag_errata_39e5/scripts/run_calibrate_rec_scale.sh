#!/usr/bin/env bash
# run_calibrate_rec_scale.sh -- §九 receiver_scale calibration (NOT hardcoded).
#
# Runs board_calibrate_rec_scale: digital-loopbacks a fixed-amplitude CW tone,
# measures the received ADC RMS in counts, and prints the receiver_scale that maps
# that reference onto the model's RMS==1.0 input domain.  Repeat the run a few
# times and confirm rec_scale is stable (see docs/RECEIVER_SCALE_CALIBRATION.md);
# the value is then passed to Gate 9 via --rec-scale (never baked into the chain).
#
# Output: a REC_SCALE line + GATE_RESULT line on stdout, and (by default)
# rec_scale.txt written into $ROOT.
#
# Exit code: the binary's own (0/1/2 = pass / fail / device-not-found).
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$(require_bin board_calibrate_rec_scale)"
require_libiio_runtime
banner "§九 receiver_scale calibration (digital loopback reference)"

exec "$BIN" \
    --samples=100000 \
    --tone=10000 \
    --rx-gain=10 \
    --tx-amp=1500 \
    --target-rms=1.0 \
    --out="$ROOT/rec_scale.txt" \
    "$@"
