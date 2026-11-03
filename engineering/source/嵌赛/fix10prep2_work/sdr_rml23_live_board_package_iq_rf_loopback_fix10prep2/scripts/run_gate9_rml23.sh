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
# For --phase=synthetic-iq (Stage G: no-RF digital injection, opens no IIO/SDR and
# starts no TX), the routes are chosen by --source x --inject-point:
#   ./run_gate9_rml23.sh --phase=synthetic-iq --source=radioml \
#       --inject-point=model-input --radioml-bin-dir DIR        # route A
#   ./run_gate9_rml23.sh --phase=synthetic-iq --source=generated \
#       --inject-point=model-input [--modulation ..] [--norm ..] [--seed ..]   # route B
#   ./run_gate9_rml23.sh --phase=synthetic-iq --source=generated \
#       --inject-point=raw-rx [--raw-complex-rms-counts ..]    # route C
#   ./run_gate9_rml23.sh --phase=synthetic-iq --source=radioml \
#       --inject-point=raw-rx-reconstructed \
#       --radioml-bin-dir DIR --roundtrip-out-dir DIR \
#       [--interpolation-factor 20] [--raw-complex-rms-counts 16] \
#       [--rec-scale ..] [--edge-policy zero|reflect]          # route D (round-trip)
# Route A requires the host-side extraction (scripts/extract_radioml_stage_g.py);
# passing the .hdf5 directly is refused (RADIOML_HDF5_HOST_EXTRACTION_REQUIRED).
# Route D reuses the SAME extracted directory (requirement 1: identical frozen
# test tensor/source_index/label/SNR) and additionally writes its artifacts +
# roundtrip_manifest.tsv to --roundtrip-out-dir (then analyze on the host with
# scripts/analyze_roundtrip_stage_g.py).  A/B/C/D are reported as model-confusion
# measurements -- there is NO accuracy PASS threshold; the gate only checks the
# injection mechanics + NPU discipline.
#
# Route C can additionally PERSIST the exact post-quantization int16 block it
# pushed into the production PreprocessChain (Stage H-E hard requirement 1) by
# passing --raw-iq-out-dir DIR: it writes generated_2p56m_<MOD>.ci16 (interleaved
# int16 LE, I0,Q0,I1,Q1...) plus a 24-column iq_loopback_manifest.tsv sidecar with
# a 3-way SHA (in-memory == on-disk == re-read), the tensor/logits SHA identity,
# and the frozen classification reference.  Default OFF (no effect otherwise):
#   ./run_gate9_rml23.sh --phase=synthetic-iq --source=generated \
#       --inject-point=raw-rx --raw-iq-out-dir DIR                  # route C persist
#
# For --phase=iq-digital-loopback (Stage H-E / Route E: same-device modulated-IQ
# digital loopback over the FROZEN Stage G int16), pass the input kind + frozen
# artifacts dir.  Route E NEVER re-generates a waveform (missing file fails closed
# with STAGE_G_FROZEN_IQ_REQUIRED).  It reports THREE separate verdicts --
# infrastructure / fidelity / classification -- never an accuracy gate:
#   ./run_gate9_rml23.sh --phase=iq-digital-loopback \
#       --input-kind=generated-2p56m --frozen-dir DIR             # Route C frozen
#   ./run_gate9_rml23.sh --phase=iq-digital-loopback \
#       --input-kind=radioml-reconstructed-2p56m --frozen-dir DIR  # Route D frozen
# arbitrary_modulated_iq_fidelity=BOARD_REQUIRED and RF_LEAKAGE_NOT_PROVEN are
# printed; digital-loopback IQ fidelity can only be finalised by this board run.
#
# For --phase=iq-pc-tx-board-rx-23class-fix10 (fix10prep2: the REAL dual-SDR
# topology -- a Windows PC owns the TX SDR, this board owns the RX SDR), pass the
# PC TX service address and the frozen D2 artifacts; this board side opens ONLY an
# RX SDR (no TX API):
#   ./run_gate9_rml23.sh --phase=iq-pc-tx-board-rx-23class-fix10 \
#       --tx-control=tcp://<PC_IP>:39010 --rx-uri="<BOARD_RX_URI>" \
#       --input-kind=radioml-d2-2p56m --frozen-dir="$D2_SMOKE_DIR" \
#       --baseline=route_f_fix9r_exact_baseline.tsv --center=2400000000 \
#       --rx-gain=30 --rf-path=direct-cable --rf-tx-target-rms=2048 \
#       --diagnostic-classes=BPSK,4ASK --out-dir=/root/fix10_pc_tx_board_rx_smoke
# The legacy single-process dual-SDR phase --phase=iq-dual-sdr-23class-fix10 is
# REJECTED on the board (result=REJECTED reason=TOPOLOGY_NOT_DEPLOYED).
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
