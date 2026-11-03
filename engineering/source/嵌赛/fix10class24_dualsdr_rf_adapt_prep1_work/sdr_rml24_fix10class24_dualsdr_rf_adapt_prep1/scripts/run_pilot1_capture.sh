#!/usr/bin/env bash
# run_pilot1_capture.sh -- M29-RML24-REALRF-FINETUNE-PILOT1 (line B): board-side RX
# capture runner for ONE session's 240 frames.  This is the board peer of the PC TX
# service host_tools/pc_tx_radioml_dualsdr.py -- the SAME real dual-SDR topology as
# iq-pc-tx-board-rx-24class-bf16-fix10, but it is a CAPTURE (never a judgement).
#
# The board opens ONLY the RX SDR; the PC owns the TX SDR.  Both ends exchange only
# control messages + sample identity + SHA over TCP (--tx-control).  Per source_id it
# writes a 32-field save-before-gate TSV row plus raw_rx.i16 / model_input.bin /
# logits.bin, and leaves digital_pred / digital_label_correct empty for offline
# Host backfill.  The six-way terminal judgement (FINETUNE_PROMISING / MARGINAL /
# NO_GENERALIZATION / ...) is done OFFLINE by line_c judge_realrf_pilot.py, never here.
#
# Required per-invocation args (the C++ runner fail-closes if any is missing):
#   --tx-manifest=<tx_manifest.tsv>   the 3-col per-session manifest (S1..S4)
#   --out-dir=<dir>                   writable base dir for save-before-gate outputs
#   --tx-control=tcp://<PC_IP>:39010  PC TX service address
#   --rx-uri=<board RX device uri>    e.g. "ip:192.168.2.1"
#   --rf-path=direct-cable            MUST be direct-cable (50-ohm SMA coax)
# Optional (defaults in the C++ runner):
#   --center=2400000000 --rx-gain=35.0 --rx-bw=18000000
#   --delay-margin=8192 --rf-noise-complex=... --input-kind=radioml-finetune-pilot1
#
# Example (board, serial COM12; PC TX service already listening):
#   ./run_pilot1_capture.sh \
#       --tx-manifest=/root/pilot1/tx_payload/S1/tx_manifest.tsv \
#       --out-dir=/root/pilot1/capture/S1 \
#       --tx-control=tcp://192.168.1.10:39010 \
#       --rx-uri="ip:192.168.2.1" --rf-path=direct-cable
#
# Exit code: the binary's own (0/1/2 = pass / fail / device-not-found).
set -euo pipefail
. "$(dirname "$0")/common_rml23.sh"

BIN="$(require_bin board_gate9_full_chain_rml23)"
require_libiio_runtime

# Frozen 24-class BF16 model (the pilot1 classification source), NOT the RML23
# 23-class model that common_rml23.sh defaults to.  SHA from
# model_rml24_bf16/model_SHA256SUMS.txt (byte-identical across every pilot1 run).
MODEL_JSON_24="$ROOT/model_rml24_bf16/rml24_adamrv11_bf16.json"
MODEL_RAW_24="$ROOT/model_rml24_bf16/rml24_adamrv11_bf16.raw"
MODEL_RAW_SHA_24="c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

banner "M29-RML24-REALRF-FINETUNE-PILOT1 board RX capture (line B)"

exec "$BIN" \
    --phase=iq-pc-tx-board-rx-24class-finetune-pilot1 \
    --model-json="$MODEL_JSON_24" \
    --model-raw="$MODEL_RAW_24" \
    --model-sha="$MODEL_RAW_SHA_24" \
    "$@"
