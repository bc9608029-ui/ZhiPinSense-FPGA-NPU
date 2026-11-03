#!/usr/bin/env bash
# run_gate9.sh -- Gate 9: the full twelve-class SDR -> NPU -> UI chain, in three
# phases (see board_gate9_full_chain_12class.cpp header).
#
#   ./run_gate9.sh --phase=offline   replay golden inputs -> NPU -> UI (strongest:
#                                    proves NPU -> UI against known inputs)
#   ./run_gate9.sh --phase=digital   Pluto digital loopback -> preprocess -> NPU -> UI
#                                    (gates CHAIN LIVENESS, never classification)
#   ./run_gate9.sh --phase=rf        external RF loopback -- REQUIRES
#                                    --confirm-safe-rf-path (refused otherwise)
#
# For --phase=digital/rf, pass the §九-calibrated receiver_scale via --rec-scale
# (run_calibrate_rec_scale.sh), e.g.:
#   ./run_gate9.sh --phase=digital --rec-scale=4.096
# The default --rec-scale 1.0 keeps the chain running but does NOT match the
# model's RMS==1.0 input domain; it is only for mechanical smoke.
#
# PASS criteria: offline -> frames==count, match_rate>=--min-match-rate, all valid;
#                digital/rf -> frames==--frames, all valid, no stream anomaly,
#                tone present, and (rf) --confirm-safe-rf-path actually given.
#
# Exit code: the binary's own (0/1/2 = pass / fail / device-not-found).
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$(require_bin board_gate9_full_chain_12class)"
require_libiio_runtime
banner "Gate 9: full chain (SDR -> NPU -> UI)"

# Defaults are --key=value; a later occurrence wins, so a user's post-script args
# (e.g. --phase=digital) override these defaults.
exec "$BIN" \
    --model-json="$MODEL_JSON" \
    --model-raw="$MODEL_RAW" \
    --model-sha="$MODEL_RAW_SHA" \
    --golden="$GOLDEN" \
    --count=240 \
    --min-match-rate=0.90 \
    --phase=offline \
    --frames=16 \
    --tone=10000 \
    --rx-gain=10 \
    --rec-scale=1.0 \
    "$@"
